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

from functools import lru_cache
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Callable, cast
import inspect
import json
import uuid

from weaviate.exceptions import WeaviateQueryError, WeaviateBaseError
from weaviate import WeaviateAsyncClient, connect_to_weaviate_cloud, connect_to_local
from weaviate.classes.init import Auth
from weaviate.exceptions import WeaviateQueryError
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.classes.config import Configure, Property, DataType

from config.embeddings import openai_embedder
from config.langfuse import provide_callback_handler_with_tags
from config import app_settings


from pydantic import BaseModel


HI_SIM = 0.92  # “sure” threshold
LO_SIM = 0.40  # “maybe” threshold
ALIAS_CLASS = "Alias"  # Weaviate collection name

EmbedderFn = Callable[[str], List[float]]
_logger = logging.getLogger("identity_async")


@dataclass
class AliasTask:
    cypher_template_id: str
    render_slots: Dict[str, Any]
    entity_id: str
    alias_text: str
    entity_type: str
    chapter: int
    chunk_id: str
    snippet: str


class BulkResolveResult(BaseModel):
    mapped_slots: Dict[str, Any]
    alias_tasks: List[AliasTask]


class LLMDecision(BaseModel):
    action: Literal["use", "new"]
    entity_id: Optional[str] = None
    alias_text: Optional[str] = None


class IdentityService:
    def __init__(
        self,
        weaviate_async_client: WeaviateAsyncClient,
        embedder: EmbedderFn | None,
        *,
        llm_disambiguator: Callable[[str, List[Dict[str, Any]]], Dict[str, Any]],
        callback_handler=None,
    ):
        self.w = weaviate_async_client
        self.embedder = embedder
        self.llm_disambiguator = llm_disambiguator
        self.callback_handler = callback_handler

    async def startup(self) -> None:
        if await self._collection_exists(ALIAS_CLASS):
            return
        self.w.collections.create(
            name=ALIAS_CLASS,
            description="Stores all known aliases for story entities",
            vectorizer_config=Configure.Vectorizer.none(),
            inverted_index_config=Configure.inverted_index(index_property_length=True),
            properties=[
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
        mapped_slots = dict(slots)
        alias_tasks: List[AliasTask] = []

        for field, raw_val in slots.items():
            etype = _FIELD_TO_ENTITY.get(field)
            if not etype:
                continue

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
        cypher_snippets: List[str] = []
        for task in alias_tasks:
            await self._upsert_alias(task)
            snippet = _render_alias_cypher(task)
            if snippet:
                cypher_snippets.append(snippet)
        return cypher_snippets

    async def _resolve_single(
        self,
        raw_name: str,
        entity_type: str,
        *,
        chapter: int,
        chunk_id: str,
        snippet: str,
    ) -> Dict[str, Any]:
        cand = await self._nearest_alias(raw_name, entity_type, limit=3)
        best = cand[0] if cand else None

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

    async def _collection_exists(self, name: str) -> bool:
        for col in await self.w.collections.list_all():
            if getattr(col, "name", col) == name:
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
            collection = self.w.collections.get(ALIAS_CLASS)
            res = await collection.query.near_vector(
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
        hits.sort(key=lambda x: -float(cast(float, x["score"])))
        return hits

    async def _llm_disambiguate(
        self,
        raw_name: str,
        aliases: List[Dict[str, Any]],
        chapter: int,
        snippet: str,
    ) -> LLMDecision:
        llm = self.llm_disambiguator
        config = (
            {"callbacks": [self.callback_handler]} if self.callback_handler else None
        )
        if hasattr(llm, "ainvoke"):
            result = await llm.ainvoke(
                {
                    "raw_name": raw_name,
                    "aliases": aliases,
                    "chapter": chapter,
                    "snippet": snippet,
                },
                config=config,
            )
        elif hasattr(llm, "invoke"):
            result = llm.invoke(
                {
                    "raw_name": raw_name,
                    "aliases": aliases,
                    "chapter": chapter,
                    "snippet": snippet,
                },
                config=config,
            )
        elif inspect.iscoroutinefunction(llm):
            result = await llm(raw_name, aliases)
        else:
            result = llm(raw_name, aliases)

        if isinstance(result, str):
            result = json.loads(result)
        if isinstance(result, dict):
            return LLMDecision(**result)
        if isinstance(result, LLMDecision):
            return result
        raise ValueError("Invalid LLM disambiguation result")

    async def _upsert_alias(self, task: AliasTask) -> None:
        col = self.w.collections.get(ALIAS_CLASS)
        props = {
            "alias_text": task.alias_text,
            "entity_id": task.entity_id,
            "entity_type": task.entity_type,
            "canonical": task.render_slots.get("canonical", False),
            "chapter": task.chapter,
            "chunk_id": task.chunk_id,
            "snippet": task.snippet,
        }
        vec = self.embedder(task.alias_text) if self.embedder else None
        try:
            await col.data.insert(properties=props, vector=vec)
        except WeaviateBaseError:
            pass


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


@lru_cache(maxsize=1)
def get_identity_service_async(
    llm_disambiguator: Optional[
        Callable[[str, List[Dict[str, Any]]], Dict[str, Any]]
    ] = None,
    embedder: EmbedderFn | None = None,
    wclient: Optional[WeaviateAsyncClient] = None,
) -> IdentityService:
    """Асинхронно создаёт и возвращает IdentityService с подключением к Weaviate."""
    disambiguator = llm_disambiguator or (lambda *_: {"action": "new"})
    handler = provide_callback_handler_with_tags(tags=[IdentityService.__name__])
    embedder = embedder or openai_embedder

    if not wclient:
        wclient = connect_to_weaviate_cloud(
            cluster_url=app_settings.WEAVIATE_URL,
            auth_credentials=Auth().api_key(api_key=app_settings.WEAVIATE_API_KEY),
        )

    return IdentityService(
        weaviate_async_client=wclient,
        embedder=embedder,
        llm_disambiguator=disambiguator,
        callback_handler=handler,
    )
