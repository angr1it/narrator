from __future__ import annotations
from uuid import uuid4

"""TemplateService — high‑level helper around Weaviate that stores and retrieves
CypherTemplate objects.

"""

from typing import Callable, List, Optional, Sequence, Dict, Any
import os

import weaviate
from weaviate.exceptions import UnexpectedStatusCodeException
import weaviate.classes as wvc
from weaviate.classes.config import Configure
from weaviate.classes.query import Filter
from weaviate.collections.classes.internal import ObjectSingleReturn

from schemas.cypher import (
    CypherTemplate,
    CypherTemplateBase,
    SlotDefinition,
    FactDescriptor,
)  # noqa: F401

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
        """Create *or* update a template in Weaviate.

        * If the object exists → do a *PATCH* update.
        * If not → create it (vector supplied if present or computable).
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
                near_vector=vector, limit=k, filters=filters
            )
        else:
            results = coll.query.near_text(query=query, limit=k, filters=filters)

        return [self._from_weaviate(obj) for obj in results.objects]

    def _ensure_schema(self) -> None:
        if self.client.collections.exists(self.CLASS_NAME):
            return

        self.client.collections.create(
            name=self.CLASS_NAME,
            description="Template that maps narrative text to Cypher code and optional Fact creation.",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            inverted_index_config=Configure.inverted_index(index_property_length=True),
            properties=[
                wvc.config.Property(name="name", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="version", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="description", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(name="details", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="category", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(
                    name="slots",
                    data_type=wvc.config.DataType.OBJECT,
                    nested_properties=[
                        wvc.config.Property(
                            name="name", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="type", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="description", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="required", data_type=wvc.config.DataType.BOOL
                        ),
                        wvc.config.Property(
                            name="default", data_type=wvc.config.DataType.TEXT
                        ),
                    ],
                ),
                wvc.config.Property(name="cypher", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="fact_descriptor",
                    data_type=wvc.config.DataType.OBJECT,
                    nested_properties=[
                        wvc.config.Property(
                            name="predicate", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="subject", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="value", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="object", data_type=wvc.config.DataType.TEXT
                        ),
                    ],
                ),
                wvc.config.Property(name="author", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="created_at", data_type=wvc.config.DataType.DATE
                ),
                wvc.config.Property(
                    name="updated_at", data_type=wvc.config.DataType.DATE
                ),
            ],
        )

    @staticmethod
    def _canonicalise_template(tpl: CypherTemplateBase) -> str:
        """Return a **stable** string representation that feeds the embedder.

        The canonical form concatenates the key semantic elements separated by
        `‖` (U+2016) so that small field order changes do not alter the meaning.
        """
        parts = [tpl.title, tpl.description or ""]
        if tpl.details:
            parts.append(tpl.details)
        parts.extend(f"{s.name}:{s.type}" for s in tpl.slots)
        if tpl.fact_descriptor:
            fd = tpl.fact_descriptor
            parts.append(f"FACT:{fd.predicate}:{fd.subject}:{fd.value}")
        return " ‖ ".join(parts)

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
            "fact_descriptor",
            "author",
            "created_at",
            "updated_at",
            "vector",
        }
        clean = {k: v for k, v in props.items() if k in allowed}
        clean["id"] = str(raw.uuid)
        return CypherTemplate(**clean)
