from __future__ import annotations

"""TemplateService — high‑level helper around Weaviate that stores and retrieves
CypherTemplate objects.

Key differences from the original implementation
------------------------------------------------
1. **Updated data model** — `CypherTemplate` now follows the spec in
   `cypher_template_and_fact.md`: `slots` (list of `SlotDefinition`), optional
   `fact_descriptor`, no more `slot_schema` / `fact_policy`. The service uses
   the new model in all public signatures.
2. **Vector search by raw text** — `top_k()` embeds the *query text* using a
   pluggable `embedder` callable (e.g. OpenAI or Cohere). It then performs a
   `nearVector` HNSW search in Weaviate, which is far more precise than the
   generic `nearText` previously used.
3. **Upsert semantics** — `upsert()` transparently handles *create* vs *update*
   via a 422 catch. It also writes the template's own vector (embedding of the
   canonicalised template string) if present or computable.
4. **Schema bootstrap** — `_ensure_schema()` will create the `CypherTemplate`
   class with the correct property types if it is missing. This keeps local
   dev environments self‑healing.

The class is now production‑ready yet minimal enough to be unit‑tested in
isolation. No other modules need to change to consume it.
"""

from typing import Callable, List, Optional, Sequence, Dict, Any
import os

import weaviate
from weaviate.exceptions import UnexpectedStatusCodeException

from schemas.cypher import CypherTemplate, SlotDefinition, FactDescriptor  # noqa: F401


EmbedderFn = Callable[[str], List[float]]  # opaque function → 1536‑d vector


class TemplateService:  # noqa: D101 – docstring at module level
    CLASS_NAME = "CypherTemplate"

    def __init__(
        self,
        weaviate_url: str,
        embedder: Optional[EmbedderFn] = None,
        openai_api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        """Create the service.

        Parameters
        ----------
        weaviate_url
            Full URL of the Weaviate instance, e.g. ``http://localhost:8080``.
        embedder
            Optional callable that takes raw text and returns an embedding
            vector. If *None* the service falls back to ``nearText`` search.
        openai_api_key_env
            Name of the env var that stores the OpenAI key. Passed as header so
            that Weaviate can call the `/v1/embeddings` endpoint if it hosts an
            *internal* vectoriser module (e.g. `text2vec-openai`).
        """
        additional_headers = None
        api_key = os.getenv(openai_api_key_env)
        if api_key:
            additional_headers = {"X-OpenAI-Api-Key": api_key}

        self.client = weaviate.Client(url=weaviate_url, additional_headers=additional_headers)  # type: ignore[arg-type]
        self.embedder = embedder
        self._ensure_schema()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def upsert(self, tpl: CypherTemplate) -> None:
        """Create *or* update a template in Weaviate.

        * If the object exists → do a *PATCH* update.
        * If not → create it (vector supplied if present or computable).
        """
        # Convert to a plain JSON‑serialisable dict (skip None values)
        payload: Dict[str, Any] = tpl.model_dump(mode="json", exclude_none=True)

        # Ensure we have a vector (either provided in the model or generated)
        if tpl.vector is None and self.embedder is not None:
            tpl.vector = self.embedder(self._canonicalise_template(tpl))
            payload["vector"] = tpl.vector
        elif tpl.vector is not None:
            payload["vector"] = tpl.vector

        try:
            self.client.data_object.create(
                class_name=self.CLASS_NAME,
                uuid=tpl.id,
                data_object=payload,
                vector=tpl.vector,
            )
        except UnexpectedStatusCodeException as exc:
            # ➜ 422 = already exists → *update* instead of *create*
            if exc.status_code == 422:
                self.client.data_object.update(
                    uuid=tpl.id,
                    class_name=self.CLASS_NAME,
                    data_object=payload,
                    vector=tpl.vector,
                )
            else:
                raise  # re‑throw anything else – connectivity, auth, etc.

    # .................................................................
    def get(self, tpl_id: str) -> CypherTemplate:
        """Retrieve a template by *ID* (raises ValueError if not found)."""
        obj = self.client.data_object.get_by_id(tpl_id, class_name=self.CLASS_NAME)
        if obj is None:
            raise ValueError(f"Template with id '{tpl_id}' not found in Weaviate.")
        return CypherTemplate(**obj["properties"])  # type: ignore[arg-type]

    # .................................................................
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

        # ----- Build the base query -------------------------------------
        props = [
            "id",
            "version",
            "title",
            "description",
            "category",
            "slots { name type description required default }",
            "cypher",
            "fact_descriptor { predicate subject value object }",
            "author",
            "created_at",
            "updated_at",
            "vector",
        ]

        if self.embedder is not None:
            vec = self.embedder(query)
            qb = (
                self.client.query.get(self.CLASS_NAME, props)
                .with_near_vector({"vector": vec})
                .with_limit(k)
            )
        else:
            qb = (
                self.client.query.get(self.CLASS_NAME, props)
                .with_near_text({"concepts": [query]})
                .with_limit(k)
            )

        if category:
            qb = qb.with_where(
                {
                    "path": ["category"],
                    "operator": "Equal",
                    "valueString": category,
                }
            )

        result = qb.do()
        data: Sequence[Dict[str, Any]] = (
            result.get("data", {}).get("Get", {}).get(self.CLASS_NAME, [])  # type: ignore[call-arg]
        )
        return [self._from_weaviate(item) for item in data]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        """Create the `CypherTemplate` class in Weaviate if it doesn't exist."""
        if self.client.schema.contains(self.CLASS_NAME):
            return  # schema is already present – nothing to do

        # A minimal schema. Nested objects (`slots`, `fact_descriptor`) are
        # stored as *objects* to preserve structure without flattening.
        schema = {
            "class": self.CLASS_NAME,
            "description": "Template that maps narrative text to Cypher code and optional Fact creation.",
            "vectorizer": "none",  # vectors are supplied by us ↗
            "properties": [
                {"name": "id", "dataType": ["string"]},
                {"name": "version", "dataType": ["string"]},
                {"name": "title", "dataType": ["text"]},
                {"name": "description", "dataType": ["text"]},
                {"name": "category", "dataType": ["text"]},
                {
                    "name": "slots",
                    "dataType": ["object"],
                    "nestedProperties": [
                        {"name": "name", "dataType": ["string"]},
                        {"name": "type", "dataType": ["string"]},
                        {"name": "description", "dataType": ["text"]},
                        {"name": "required", "dataType": ["boolean"]},
                        {"name": "default", "dataType": ["text"]},
                    ],
                },
                {"name": "cypher", "dataType": ["text"]},
                {
                    "name": "fact_descriptor",
                    "dataType": ["object"],
                    "nestedProperties": [
                        {"name": "predicate", "dataType": ["string"]},
                        {"name": "subject", "dataType": ["string"]},
                        {"name": "value", "dataType": ["string"]},
                        {"name": "object", "dataType": ["string"]},
                    ],
                },
                {"name": "author", "dataType": ["string"]},
                {"name": "created_at", "dataType": ["date"]},
                {"name": "updated_at", "dataType": ["date"]},
            ],
        }
        self.client.schema.create_class(schema)

    # .................................................................
    @staticmethod
    def _canonicalise_template(tpl: CypherTemplate) -> str:
        """Return a **stable** string representation that feeds the embedder.

        The canonical form concatenates the key semantic elements separated by
        `‖` (U+2016) so that small field order changes do not alter the meaning.
        """
        parts = [tpl.title, tpl.description]
        parts.extend(f"{s.name}:{s.type}" for s in tpl.slots)
        if tpl.fact_descriptor:
            parts.append(
                f"FACT:{tpl.fact_descriptor.predicate}:{tpl.fact_descriptor.subject}:{tpl.fact_descriptor.value}"
            )
        return " ‖ ".join(parts)

    # .................................................................
    @staticmethod
    def _from_weaviate(raw: Dict[str, Any]) -> CypherTemplate:
        """Convert Weaviate's nested dict to a ``CypherTemplate`` instance."""
        props = raw.get(
            "properties", raw
        )  # SDK returns either {"properties": …} or inline
        # No transformation is required – keys match the Pydantic model.
        # We *remove* extra keys that the model does not expect.
        allowed = {
            "id",
            "version",
            "title",
            "description",
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
        return CypherTemplate(**clean)
