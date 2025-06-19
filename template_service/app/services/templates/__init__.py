from __future__ import annotations
from uuid import uuid4
from functools import lru_cache

from services.templates.warning import log_low_score_warning
from utils.logger import get_logger

"""High-level helper around Weaviate that stores and retrieves ``CypherTemplate`` objects.

Each template describes how to transform extracted slots into graph relations.
The service is responsible for persisting additional metadata such as
``graph_relation``, ``attachment_policy`` and ``default_confidence`` which are
used by the extraction pipeline.
"""

from typing import Callable, List, Optional, Dict, Any
from schemas.cypher import TemplateRenderMode
import asyncio

import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import Filter
from weaviate.collections.classes.internal import ObjectSingleReturn
from weaviate.classes.query import MetadataQuery

from schemas.cypher import (
    CypherTemplate,
    CypherTemplateBase,
)

logger = get_logger(__name__)

EmbedderFn = Callable[[str], List[float]]  # opaque function → 1536‑d vector


class TemplateService:

    def __init__(
        self,
        weaviate_client: Optional[weaviate.Client] = None,
        embedder: Optional[EmbedderFn] = None,
        class_name: str = "CypherTemplate",
    ) -> None:
        """Create the service.

        Parameters
        ----------
        weaviate_client
            Weaviate client to use.
        embedder
            Optional callable that takes raw text and returns an embedding
            vector. If *None* the service falls back to ``nearText`` search.
        """

        self.client: weaviate.Client | None = weaviate_client
        self.CLASS_NAME = class_name
        self.embedder = embedder
        self._ensure_schema()
        self.ensure_base_templates()

    def upsert(self, tpl: CypherTemplateBase) -> None:
        """Create or update a template in Weaviate.

        The ``CypherTemplateBase`` object may include ``graph_relation`` and
        other fields required by the pipeline.  If a template with the same
        ``name`` already exists the method performs a partial update; otherwise a
        new object is inserted.  Embeddings are generated automatically when an
        embedder is configured.
        """
        tpl.validate_extract()
        tpl.validate_augment()

        # Формируем payload без uuid
        payload: Dict[str, Any] = tpl.model_dump(
            mode="json", exclude_none=True, exclude={"uuid"}
        )

        # Добавляем вектор при необходимости
        if payload.get("vector") is None and self.embedder:
            payload["vector"] = self.embedder(tpl.representation or tpl.description)  # type: ignore[arg-type]

        assert self.client is not None
        coll = self.client.collections.get(self.CLASS_NAME)  # type: ignore[attr-defined]

        # Ищем существующий объект по полю 'name'
        existing = coll.query.fetch_objects(
            filters=Filter.by_property("name").equal(tpl.name), limit=1
        ).objects

        if existing:
            # Обновляем существующий объект
            uuid = existing[0].uuid
            coll.data.update(
                uuid=uuid, properties=payload, vector=payload.get("vector")
            )
        else:
            # Вставляем новый объект и получаем его UUID
            uuid = getattr(tpl, "uuid", None) or str(uuid4())
            uuid = coll.data.insert(
                properties=payload, uuid=uuid, vector=payload.get("vector")
            )

        return CypherTemplate(id=uuid, **payload)  # type: ignore[arg-type]

    async def upsert_async(self, tpl: CypherTemplateBase) -> CypherTemplate:
        """Thread off :meth:`upsert` for use in async code."""
        return await asyncio.to_thread(self.upsert, tpl)

    def get(self, id: str) -> CypherTemplate:
        assert self.client is not None
        coll = self.client.collections.get(self.CLASS_NAME)  # type: ignore[attr-defined]
        obj = coll.query.fetch_object_by_id(id)
        if not obj:
            raise ValueError(f"Template {id} not found")
        return self._from_weaviate(obj)

    async def get_async(self, id: str) -> CypherTemplate:
        """Async wrapper around :meth:`get`."""
        return await asyncio.to_thread(self.get, id)

    def get_by_name(self, name: str) -> CypherTemplate:
        assert self.client is not None
        coll = self.client.collections.get(self.CLASS_NAME)  # type: ignore[attr-defined]
        res = coll.query.fetch_objects(
            filters=Filter.by_property("name").equal(name), limit=1
        ).objects
        if not res:
            raise ValueError(f"Template '{name}' not found")
        return self._from_weaviate(res[0])

    async def get_by_name_async(self, name: str) -> CypherTemplate:
        """Async wrapper around :meth:`get_by_name`."""
        return await asyncio.to_thread(self.get_by_name, name)

    def top_k(
        self,
        query: str,
        category: Optional[str] = None,
        k: int = 10,
        top_score_threshold_warn: float = 0.33,
        score_threshold: float = 0.33,
        *,
        alpha: float = 0.5,
        mode: TemplateRenderMode = TemplateRenderMode.EXTRACT,
    ) -> List[CypherTemplate]:
        """Semantic search for the *k* best‑matching templates.

        The method performs an **HNSW vector search** if an embedder is
        configured; otherwise it uses Weaviate's ``nearText`` fallback which is
        less precise but still acceptable for local dev.
        """
        if k <= 0:
            return []

        assert self.client is not None
        coll = self.client.collections.get(self.CLASS_NAME)  # type: ignore[attr-defined]

        # Определяем фильтры, если указана категория
        filters = Filter.by_property("category").equal(category) if category else None
        if mode is TemplateRenderMode.AUGMENT:
            aug_filter = Filter.by_property("supports_augment").equal(True)
            filters = (
                aug_filter if filters is None else Filter.all_of([filters, aug_filter])
            )

        vector = self.embedder(query) if self.embedder else None
        results = coll.query.hybrid(
            query=query,
            vector=vector,
            alpha=alpha,
            query_properties=["keywords"],
            filters=filters,
            limit=k,
            return_metadata=MetadataQuery(score=True, distance=True),
        )

        if not results.objects:
            return []

        objects = results.objects
        top_score = (
            getattr(objects[0].metadata, "score", 0.0) if objects[0].metadata else 0.0
        )

        if top_score < top_score_threshold_warn:
            log_low_score_warning(
                query,
                objects,
                [getattr(obj.metadata, "score", None) for obj in objects],
                score_threshold,
            )

        filtered = []
        for obj in objects:
            score = getattr(obj.metadata, "score", None)
            if score is None or score >= score_threshold:
                filtered.append(self._from_weaviate(obj))
        return filtered

    async def top_k_async(
        self,
        query: str,
        category: Optional[str] = None,
        k: int = 10,
        top_distance_threshold_warn: float = 0.33,
        distance_threshold: float = 0.33,
        *,
        alpha: float = 0.5,
        mode: TemplateRenderMode = TemplateRenderMode.EXTRACT,
    ) -> List[CypherTemplate]:
        """Async wrapper around :meth:`top_k`."""
        return await asyncio.to_thread(
            self.top_k,
            query,
            category,
            k,
            top_distance_threshold_warn,
            distance_threshold,
            alpha=alpha,
            mode=mode,
        )

    def ensure_base_templates(self) -> None:
        """Load built-in templates into the collection if possible."""
        if not self.client:
            return
        try:
            from templates.base import base_templates
            from templates.imports import import_templates

            import_templates(self, base_templates)
        except Exception as exc:  # pragma: no cover - log but continue
            logger.warning(f"Failed to import base templates: {exc}")

    def _ensure_schema(self) -> None:
        if self.client and self.client.collections.exists(self.CLASS_NAME):  # type: ignore[attr-defined]
            return
        if not self.client:
            return

        self.client.collections.create(  # type: ignore[attr-defined]
            name=self.CLASS_NAME,
            description="Template that maps narrative text to Cypher code.",
            vectorizer_config=Configure.Vectorizer.none(),
            inverted_index_config=Configure.inverted_index(index_property_length=True),
            properties=[
                Property(name="name", data_type=DataType.TEXT),
                Property(name="version", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
                Property(name="description", data_type=DataType.TEXT),
                Property(
                    name="keywords",
                    data_type=DataType.TEXT_ARRAY,
                    index_searchable=True,
                ),
                Property(name="category", data_type=DataType.TEXT),
                Property(
                    name="slots",
                    data_type=DataType.OBJECT,
                    nested_properties=[
                        Property(name="type", data_type=DataType.TEXT),
                        Property(name="description", data_type=DataType.TEXT),
                        Property(name="required", data_type=DataType.BOOL),
                        Property(name="default", data_type=DataType.TEXT),
                    ],
                ),
                Property(name="extract_cypher", data_type=DataType.TEXT),
                Property(name="use_base_extract", data_type=DataType.BOOL),
                Property(name="augment_cypher", data_type=DataType.TEXT),
                Property(name="supports_extract", data_type=DataType.BOOL),
                Property(name="supports_augment", data_type=DataType.BOOL),
                Property(
                    name="graph_relation",
                    data_type=DataType.OBJECT,
                    nested_properties=[
                        Property(name="predicate", data_type=DataType.TEXT),
                        Property(name="subject", data_type=DataType.TEXT),
                        Property(name="value", data_type=DataType.TEXT),
                        Property(name="object", data_type=DataType.TEXT),
                    ],
                ),
                Property(name="attachment_policy", data_type=DataType.TEXT),
                Property(name="default_confidence", data_type=DataType.NUMBER),
                Property(name="author", data_type=DataType.TEXT),
                Property(name="created_at", data_type=DataType.DATE),
                Property(name="updated_at", data_type=DataType.DATE),
                Property(
                    name="return_map",
                    data_type=DataType.OBJECT,
                    nested_properties=[
                        Property(name="variable", data_type=DataType.TEXT),
                        Property(name="node_id", data_type=DataType.TEXT),
                    ],
                ),
            ],
        )

    @staticmethod
    def _from_weaviate(raw: ObjectSingleReturn) -> CypherTemplate:
        props = raw.properties
        allowed = {
            "name",
            "version",
            "title",
            "description",
            "keywords",
            "category",
            "slots",
            "extract_cypher",
            "use_base_extract",
            "augment_cypher",
            "supports_extract",
            "supports_augment",
            "graph_relation",
            "attachment_policy",
            "default_confidence",
            "author",
            "created_at",
            "updated_at",
            "vector",
            "return_map",
        }
        clean = {k: v for k, v in props.items() if k in allowed}
        if "supports_extract" not in clean:
            clean["supports_extract"] = bool(clean.get("extract_cypher"))
        if "supports_augment" not in clean:
            clean["supports_augment"] = bool(clean.get("augment_cypher"))
        clean["id"] = str(raw.uuid)
        score = None
        if raw.metadata is not None:
            score = getattr(raw.metadata, "score", None)
        clean["score"] = score
        return CypherTemplate(**clean)


@lru_cache(maxsize=1)
def get_template_service_sync(
    embedder: Optional[EmbedderFn] = None,
    wclient: Optional[weaviate.Client] = None,
) -> "TemplateService":
    """Return a cached TemplateService configured for production."""
    from config.embeddings import openai_embedder
    from config.weaviate import connect_to_weaviate
    from config import app_settings

    resolved_embedder = embedder or openai_embedder

    if not wclient:
        wclient = connect_to_weaviate(
            url=app_settings.WEAVIATE_URL,
            api_key=app_settings.WEAVIATE_API_KEY,
        )

    return TemplateService(weaviate_client=wclient, embedder=resolved_embedder)
