from __future__ import annotations
from uuid import uuid4

from services.templates.warning import log_low_score_warning

"""High-level helper around Weaviate that stores and retrieves ``CypherTemplate`` objects.

Each template describes how to transform extracted slots into graph relations.
The service is responsible for persisting additional metadata such as
``graph_relation``, ``attachment_policy`` and ``default_confidence`` which are
used by the extraction pipeline.
"""

from typing import Callable, List, Optional, Dict, Any

import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import Filter
from weaviate.collections.classes.internal import ObjectSingleReturn
from weaviate.classes.query import MetadataQuery

from schemas.cypher import (
    CypherTemplate,
    CypherTemplateBase,
)

EmbedderFn = Callable[[str], List[float]]  # opaque function → 1536‑d vector


class TemplateService:
    CLASS_NAME = "CypherTemplate"

    def __init__(
        self,
        weaviate_client: Optional[weaviate.Client] = None,
        embedder: Optional[EmbedderFn] = None,
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

        self.client: weaviate.Client = weaviate_client

        self.embedder = embedder
        self._ensure_schema()

    def upsert(self, tpl: CypherTemplateBase) -> None:
        """Create or update a template in Weaviate.

        The ``CypherTemplateBase`` object may include ``graph_relation`` and
        other fields required by the pipeline.  If a template with the same
        ``name`` already exists the method performs a partial update; otherwise a
        new object is inserted.  Embeddings are generated automatically when an
        embedder is configured.
        """
        # Формируем payload без uuid
        payload: Dict[str, Any] = tpl.model_dump(
            mode="json", exclude_none=True, exclude={"uuid"}
        )

        # Добавляем вектор при необходимости
        if payload.get("vector") is None and self.embedder:
            payload["vector"] = self.embedder(self._canonicalise_template(tpl))  # type: ignore[arg-type]

        coll = self.client.collections.get(self.CLASS_NAME)

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

    def get(self, id: str) -> CypherTemplate:
        coll = self.client.collections.get(self.CLASS_NAME)
        obj = coll.query.fetch_object_by_id(id)
        if not obj:
            raise ValueError(f"Template {id} not found")
        return self._from_weaviate(obj)

    def get_by_name(self, name: str) -> CypherTemplate:
        coll = self.client.collections.get(self.CLASS_NAME)
        res = coll.query.fetch_objects(
            filters=Filter.by_property("name").equal(name), limit=1
        ).objects
        if not res:
            raise ValueError(f"Template '{name}' not found")
        return self._from_weaviate(res[0])

    def top_k(
        self,
        query: str,
        category: Optional[str] = None,
        k: int = 3,
        distance_threshold: float = 0.5,
    ) -> List[CypherTemplate]:
        """Semantic search for the *k* best‑matching templates.

        The method performs an **HNSW vector search** if an embedder is
        configured; otherwise it uses Weaviate's ``nearText`` fallback which is
        less precise but still acceptable for local dev.
        """
        if k <= 0:
            return []

        coll = self.client.collections.get(self.CLASS_NAME)

        # Определяем фильтры, если указана категория
        filters = Filter.by_property("category").equal(category) if category else None

        # Выполняем поиск по вектору или по тексту
        if self.embedder:
            vector = self.embedder(query)
            results = coll.query.near_vector(
                near_vector=vector,
                limit=k,
                filters=filters,
                return_metadata=MetadataQuery(score=True, distance=True),
            )
        else:
            results = coll.query.near_text(
                query=query,
                limit=k,
                filters=filters,
                return_metadata=MetadataQuery(score=True, distance=True),
            )

        if not results.objects:
            return []

        objects = results.objects
        distances = [obj.metadata.distance for obj in objects]

        if distances and distances[0] > distance_threshold:
            log_low_score_warning(query, objects, distances, distance_threshold)

        return [self._from_weaviate(obj) for obj in objects]

    def _ensure_schema(self) -> None:
        if self.client.collections.exists(self.CLASS_NAME):
            return

        self.client.collections.create(
            name=self.CLASS_NAME,
            description="Template that maps narrative text to Cypher code.",
            vectorizer_config=Configure.Vectorizer.none(),
            inverted_index_config=Configure.inverted_index(index_property_length=True),
            properties=[
                Property(name="name", data_type=DataType.TEXT),
                Property(name="version", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
                Property(name="description", data_type=DataType.TEXT),
                Property(name="details", data_type=DataType.TEXT),
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
                Property(name="cypher", data_type=DataType.TEXT),
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
            ],
        )

    @staticmethod
    def _canonicalise_template(tpl: CypherTemplateBase) -> str:
        """Return a **stable** string representation that feeds the embedder.

        The canonical form concatenates the key semantic elements separated by
        `‖` (U+2016) so that small field order changes do not alter the meaning.
        """
        representation = tpl.description
        if tpl.details:
            representation += " ‖ " + tpl.details

        return representation

    @staticmethod
    def _from_weaviate(raw: ObjectSingleReturn) -> CypherTemplate:
        props = raw.properties
        allowed = {
            "name",
            "version",
            "title",
            "description",
            "details",
            "category",
            "slots",
            "cypher",
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
        clean["id"] = str(raw.uuid)
        return CypherTemplate(**clean)
