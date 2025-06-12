# flake8: noqa
"""
identity_async.py   – v0.3 (Weaviate Python client v4, async API)

Responsibilities
----------------
1.  Maintain a collection `Alias` in Weaviate (async).
2.  Provide a two-phase interface:

      • phase #1  – `resolve_bulk_for_template(…)`
        ↳ gets the *raw* slot dict (already extracted by SlotFiller)
          – returns a tuple:
              (mapped_slots,  # slot-name ➞ entity_id
               alias_tasks)   # list[AliasTask] – to be committed later

      • phase #2  – `commit_aliases(alias_tasks)`
        ↳ actually writes the alias objects (and – if needed – Cypher
          strings for “create entity” / “add alias”) and returns the list
          of Cypher statements that must be added to the batch the
          pipeline will send to Neo4j.

3.  Completely asynchronous – built on top of the official
   `weaviate.client.WeaviateAsyncClient` v4.

You *do not* need to modify calling code except:
    - call `resolve_bulk_for_template(…)`
    - pass its second result later to `commit_aliases(…)`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Callable

import uuid
import weaviate
from weaviate.client import WeaviateAsyncClient
from weaviate.exceptions import WeaviateQueryError
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.classes.config import Configure, Property, DataType

from pydantic import BaseModel


HI_SIM = 0.92  # “sure” threshold
LO_SIM = 0.40  # “maybe” threshold
ALIAS_CLASS = "Alias"  # Weaviate collection name

EmbedderFn = Callable[[str], List[float]]
_logger = logging.getLogger("identity_async")


@dataclass
class AliasTask:
    """A deferred operation that has to be materialised after template-render."""

    cypher_template_id: str  # id of Jinja2 alias template
    render_slots: Dict[str, Any]  # slots to pass into the template
    # The three fields below are already resolved & immutable:
    entity_id: str  # final canonical id
    alias_text: str
    entity_type: str
    chapter: int
    chunk_id: str
    snippet: str


class BulkResolveResult(BaseModel):
    """Return-object of `resolve_bulk_for_template`."""

    mapped_slots: Dict[str, Any]  # slot-name ➞ entity_id
    alias_tasks: List[AliasTask]  # to be committed later


class LLMDecision(BaseModel):
    action: Literal["use", "new"]
    entity_id: Optional[str] = None
    alias_text: Optional[str] = None


class IdentityService:
    """
    Canonical-name resolver, async flavour.
    Works with the template-pipeline in *two* passes.
    """

    def __init__(
        self,
        weaviate_async_client: WeaviateAsyncClient,
        embedder: EmbedderFn,
        *,
        llm_disambiguator: Callable[[str, List[Dict[str, Any]]], Dict[str, Any]],
    ):
        self.w = weaviate_async_client
        self.embedder = embedder
        self.llm_disambiguator = llm_disambiguator

    async def startup(self) -> None:
        """Ensure the ``Alias`` collection exists in Weaviate.

        Older code used ``Configure.Property`` which is not available in
        ``weaviate-client`` v4.  Here we rely on ``Property`` and ``DataType``
        from :mod:`weaviate.classes.config` so the schema creation works across
        library versions.
        """
        if await self._collection_exists(ALIAS_CLASS):
            return
        await self.w.collections.create(
            name=ALIAS_CLASS,
            description="Stores all known aliases for story entities",
            vectorizer_config=Configure.Vectorizer.none(),
            inverted_index_config=Configure.inverted_index(index_property_length=True),
            properties=[
                # NOTE all fields are TEXT unless explicitly stated
                Property(name="alias_text", data_type=DataType.TEXT),
                Property(name="entity_id", data_type=DataType.TEXT),
                Property(name="entity_type", data_type=DataType.TEXT),
                Property(name="canonical", data_type=DataType.BOOL),
                Property(name="chapter", data_type=DataType.INT),
                Property(name="chunk_id", data_type=DataType.TEXT),
                Property(name="snippet", data_type=DataType.TEXT),
            ],
        )
        _logger.info("[Identity] ➕ Collection 'Alias' created")

    async def resolve_bulk(
        self,
        slots: Dict[str, Any],
        *,
        chapter: int,
        chunk_id: str,
        snippet: str,
    ) -> BulkResolveResult:
        """Resolve entity-like slots and prepare alias records.

        Parameters
        ----------
        slots:
            Raw slot dictionary from :class:`SlotFiller`.
        chapter:
            Chapter number used for context.
        chunk_id:
            Identifier of the ``ChunkNode`` the aliases belong to.
        snippet:
            Raw text snippet where the alias appeared.

        Returns
        -------
        BulkResolveResult
            Contains ``mapped_slots`` with canonical IDs and the ``alias_tasks``
            that must be committed after rendering.
        """
        mapped_slots = dict(slots)  # copy
        alias_tasks: List[AliasTask] = []

        for field, raw_val in slots.items():
            etype = _FIELD_TO_ENTITY.get(field)
            if not etype:
                continue  # – not an entity field

            decision = await self._resolve_single(
                raw_name=str(raw_val),
                entity_type=etype,
                chapter=chapter,
                chunk_id=chunk_id,
                snippet=snippet,
            )

            mapped_slots[field] = decision["entity_id"]

            if decision["need_task"]:
                alias_tasks.append(
                    AliasTask(
                        cypher_template_id=decision["template_id"],
                        render_slots=decision["render_slots"],
                        entity_id=decision["entity_id"],
                        alias_text=decision["alias_text"],
                        entity_type=etype,
                        chapter=chapter,
                        chunk_id=chunk_id,
                        snippet=snippet,
                    )
                )

        return BulkResolveResult(mapped_slots=mapped_slots, alias_tasks=alias_tasks)

    async def commit_aliases(self, alias_tasks: List[AliasTask]) -> List[str]:
        """
        PHASE #2 – called after the entire Cypher batch for the *content* template
        was prepared.  Writes the Alias objects & returns Cypher strings to be
        appended to the template batch (if any).
        """
        cypher_snippets: List[str] = []
        for task in alias_tasks:
            await self._upsert_alias(task)
            snippet = _render_alias_cypher(task)
            if snippet:
                cypher_snippets.append(snippet)
        return cypher_snippets

    # ---------- internal helpers  ----------------------------------------- #

    async def _resolve_single(
        self,
        raw_name: str,
        entity_type: str,
        *,
        chapter: int,
        chunk_id: str,
        snippet: str,
    ) -> Dict[str, Any]:
        """
        Internal – returns a dict:
            { entity_id, alias_text, need_task: bool,
              template_id, render_slots }
        """
        cand = await self._nearest_alias(raw_name, entity_type, limit=3)
        best = cand[0] if cand else None

        # ---- CASE A: high-confidence hit -----------------------------------------
        if best and best["score"] >= HI_SIM:
            need_task = best["alias_text"] != raw_name
            return {
                "entity_id": best["entity_id"],
                "alias_text": raw_name,
                "need_task": need_task,
                "template_id": "add_alias" if need_task else None,
                "render_slots": {
                    "alias_text": raw_name,
                    "entity_id": best["entity_id"],
                    "entity_type": entity_type,
                    "canonical": False,
                },
            }

        # ---- CASE B: ambiguous hit – LLM disambiguation --------------------------
        if best and best["score"] >= LO_SIM:
            decision = await self._llm_disambiguate(raw_name, cand, chapter, snippet)
            if decision.action == "use":
                return {
                    "entity_id": decision.entity_id,
                    "alias_text": decision.alias_text or raw_name,
                    "need_task": True,
                    "template_id": "add_alias",
                    "render_slots": {
                        "alias_text": decision.alias_text or raw_name,
                        "entity_id": decision.entity_id,
                        "entity_type": entity_type,
                        "canonical": False,
                    },
                }

        # ---- CASE C: brand-new entity -------------------------------------------
        entity_id = f"{entity_type.lower()}-{uuid.uuid4().hex[:8]}"
        return {
            "entity_id": entity_id,
            "alias_text": raw_name,
            "need_task": True,
            "template_id": "create_entity_with_alias",
            "render_slots": {
                "alias_text": raw_name,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "canonical": True,
            },
        }

    # ---------- low-level Weaviate ops ------------------------------------ #

    async def _collection_exists(self, name: str) -> bool:
        for col in await self.w.collections.list_all():
            if col.name == name:
                return True
        return False

    async def _nearest_alias(
        self,
        query_text: str,
        entity_type: str,
        *,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        if not self.embedder:
            return []

        vector = self.embedder(query_text)
        try:
            res = await self.w.collections.get(ALIAS_CLASS).query.near_vector(
                near_vector=vector,
                limit=limit,
                filters=Filter.by_property("entity_type").equal(entity_type),
                return_metadata=MetadataQuery(distance=True),
            )
        except WeaviateQueryError as exc:
            _logger.error("Weaviate near-vector failed: %s", exc)
            return []

        hits = []
        for obj in res.objects:
            dst = 1.0 - (obj.metadata.distance or 0.0)
            hits.append(
                {
                    **obj.properties,
                    "score": round(dst, 4),
                }
            )
        hits.sort(key=lambda x: -x["score"])
        return hits

    async def _llm_disambiguate(
        self,
        raw_name: str,
        aliases: List[Dict[str, Any]],
        chapter: int,
        snippet: str,
    ) -> LLMDecision:  # mocked – replace w/ real model call
        # Minimal stub to keep example runnable; plug your LangChain chain here.
        # naive – always “new”
        return LLMDecision(action="new")

    async def _upsert_alias(self, task: AliasTask) -> None:
        """Write alias object – ignore duplicate key errors."""
        col = self.w.collections.get(ALIAS_CLASS)
        props = {
            "alias_text": task.alias_text,
            "entity_id": task.entity_id,
            "entity_type": task.entity_type,
            # meta – could be filled by caller if needed
            "canonical": task.render_slots.get("canonical", False),
            "chapter": task.chapter,
            "chunk_id": task.chunk_id,
            "snippet": task.snippet,
        }
        vec = self.embedder(task.alias_text) if self.embedder else None
        try:
            await col.data.insert(properties=props, vector=vec)
        except weaviate.exceptions.WeaviateBaseError:
            pass  # duplicate – ignore


# --------------------------------------------------------------------------- #
#  🔧  helpers
# --------------------------------------------------------------------------- #

_FIELD_TO_ENTITY = {
    "character": "CHARACTER",
    "source": "CHARACTER",
    "target": "CHARACTER",
    "faction": "FACTION",
    "location": "LOCATION",
}


def _render_alias_cypher(task: AliasTask) -> str:
    """Simplified – you probably have a Jinja2 template system already."""
    if task.cypher_template_id != "create_entity_with_alias":
        return ""
    return (
        f"CREATE (e:{task.entity_type} {{id:'{task.entity_id}', "
        f"name:'{task.alias_text}'}})"
    )
