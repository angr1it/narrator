from functools import lru_cache
import logging
import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Callable, cast, Union

from weaviate import WeaviateClient, connect_to_weaviate_cloud
from weaviate.classes.init import Auth
from weaviate.exceptions import WeaviateQueryError, WeaviateBaseError
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.classes.config import Configure, Property, DataType

from pydantic import BaseModel

from config.embeddings import openai_embedder, EmbedderFn  # type: ignore
from config.langfuse import provide_callback_handler_with_tags  # type: ignore
from config import app_settings  # type: ignore

_logger = logging.getLogger("identity_sync_wrapper")

HI_SIM = 0.92
LO_SIM = 0.40
ALIAS_CLASS = "Alias"


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
        weaviate_sync_client: WeaviateClient,
        embedder: Optional[EmbedderFn],
        *,
        llm: Callable[[str, List[Dict[str, Any]], int, str], Union[LLMDecision, dict]],
        callback_handler=None,
    ) -> None:
        self._w = weaviate_sync_client
        self._embedder = embedder
        self._llm = llm
        self._callback_handler = callback_handler

    async def startup(self) -> None:
        await self._run_sync(self._startup_sync)

    async def resolve_bulk(
        self,
        slots: Dict[str, Any],
        *,
        chapter: int,
        chunk_id: str,
        snippet: str,
    ) -> BulkResolveResult:
        return await self._run_sync(
            self._resolve_bulk_sync,
            slots,
            chapter,
            chunk_id,
            snippet,
        )

    async def commit_aliases(self, alias_tasks: List[AliasTask]) -> List[str]:
        # call async or sync upsert_alias and collect cypher snippets
        cyphers: List[str] = []
        for task in alias_tasks:
            upsert = getattr(self, "_upsert_alias", None)
            if callable(upsert) and asyncio.iscoroutinefunction(upsert):
                await upsert(task)
            else:
                self._upsert_alias_sync(task)
            snippet = _render_alias_cypher(task)
            if snippet:
                cyphers.append(snippet)
        return cyphers

    async def _run_sync(self, fn: Callable, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _startup_sync(self) -> None:
        if self._collection_exists(ALIAS_CLASS):
            return
        self._w.collections.create(
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
        _logger.info("[Identity] ➕ Collection 'Alias' created (sync mode)")

    def _collection_exists(self, name: str) -> bool:
        for col in self._w.collections.list_all():
            if getattr(col, "name", col) == name:
                return True
        return False

    def _resolve_bulk_sync(
        self,
        slots: Dict[str, Any],
        chapter: int,
        chunk_id: str,
        snippet: str,
    ) -> BulkResolveResult:
        mapped_slots: Dict[str, Any] = dict(slots)
        alias_tasks: List[AliasTask] = []

        for field, raw_val in slots.items():
            etype = _FIELD_TO_ENTITY.get(field)
            if not etype:
                continue

            decision = self._resolve_single_sync(
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

    def _commit_aliases_sync(self, alias_tasks: List[AliasTask]) -> List[str]:
        cypher_snippets: List[str] = []
        for task in alias_tasks:
            self._upsert_alias_sync(task)
            snippet = _render_alias_cypher(task)
            if snippet:
                cypher_snippets.append(snippet)
        return cypher_snippets

    def _resolve_single_sync(
        self,
        raw_name: str,
        entity_type: str,
        *,
        chapter: int,
        chunk_id: str,
        snippet: str,
    ) -> Dict[str, Any]:
        cand = self._nearest_alias_sync(raw_name, entity_type, limit=3)
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
            decision = self._llm_disambiguate_sync(raw_name, cand, chapter, snippet)
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

    def _nearest_alias_sync(
        self,
        query_text: str,
        entity_type: str,
        *,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        if not self._embedder:
            return []
        vector = self._embedder(query_text)
        try:
            collection = self._w.collections.get(ALIAS_CLASS)
            res = collection.query.near_vector(
                near_vector=vector,
                limit=limit,
                filters=Filter.by_property("entity_type").equal(entity_type),
                return_metadata=MetadataQuery(distance=True),
            )
        except WeaviateQueryError as exc:
            _logger.error("Weaviate near-vector failed: %s", exc)
            return []

        hits: List[Dict[str, Any]] = []
        for obj in res.objects:
            dst = 1.0 - (obj.metadata.distance or 0.0)
            hits.append({**obj.properties, "score": round(dst, 4)})
        hits.sort(key=lambda x: -float(cast(float, x["score"])))
        return hits

    def _llm_disambiguate_sync(
        self,
        raw_name: str,
        aliases: List[Dict[str, Any]],
        chapter: int,
        snippet: str,
    ) -> LLMDecision:
        result = self._llm(raw_name, aliases, chapter, snippet)
        if isinstance(result, dict):
            return LLMDecision(**result)
        if isinstance(result, LLMDecision):
            return result
        raise ValueError(f"_llm must return LLMDecision or dict, got {type(result)}")

    def _upsert_alias_sync(self, task: AliasTask) -> None:
        col = self._w.collections.get(ALIAS_CLASS)
        props = {
            "alias_text": task.alias_text,
            "entity_id": task.entity_id,
            "entity_type": task.entity_type,
            "canonical": task.render_slots.get("canonical", False),
            "chapter": task.chapter,
            "chunk_id": task.chunk_id,
            "snippet": task.snippet,
        }
        vec = self._embedder(task.alias_text) if self._embedder else None
        try:
            col.data.insert(properties=props, vector=vec)
        except WeaviateBaseError:
            pass


_FIELD_TO_ENTITY = {
    "character": "CHARACTER",
    "source": "CHARACTER",
    "target": "CHARACTER",
    "faction": "FACTION",
    "location": "LOCATION",
}


def _render_alias_cypher(task: AliasTask) -> str:
    if task.cypher_template_id != "create_entity_with_alias":
        return ""
    return f"CREATE (e:{task.entity_type} {{id:'{task.entity_id}', name:'{task.alias_text}'}})"


@lru_cache(maxsize=1)
def get_identity_service_sync(
    llm: Optional[
        Callable[[str, List[Dict[str, Any]], int, str], Union[LLMDecision, dict]]
    ] = None,
    embedder: Optional[EmbedderFn] = None,
    wclient: Optional[WeaviateClient] = None,
) -> IdentityService:
    resolved_llm = llm or (lambda *_: {"action": "new"})
    handler = provide_callback_handler_with_tags(tags=[IdentityService.__name__])
    embedder = embedder or openai_embedder

    if not wclient:
        wclient = connect_to_weaviate_cloud(
            cluster_url=app_settings.WEAVIATE_URL,
            auth_credentials=Auth().api_key(api_key=app_settings.WEAVIATE_API_KEY),
        )

    return IdentityService(
        weaviate_sync_client=wclient,
        embedder=embedder,
        llm=resolved_llm,
        callback_handler=handler,
    )
