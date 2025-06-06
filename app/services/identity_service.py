from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, List, Optional, Dict, Any

import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Configure
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.exceptions import WeaviateQueryError

from pydantic import BaseModel
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser

from core.identity.prompts import PROMPTS_ENV

logger = logging.getLogger(__name__)

EmbedderFn = Callable[[str], List[float]]

HI_SIM = 0.92
LO_SIM = 0.40
CLASS_NAME = "Alias"


@dataclass
class ResolveResult:
    entity_id: str
    alias_cypher: Optional[str] = None  # если нужно создать сущность в графе


class AliasDecision(BaseModel):
    action: str  # "use" | "new"
    entity_id: Optional[str] = None
    alias_text: Optional[str] = None
    canonical: Optional[bool] = None


class IdentityService:
    """Класс, отвечающий за канонизацию имён, управление alias'ами и синхронизацию Weaviate + Neo4j."""

    def __init__(
        self,
        weaviate_client: weaviate.Client,
        embedder: EmbedderFn,
        llm,
        tracer=None,
    ) -> None:
        self.w = weaviate_client
        self.embedder = embedder
        self.llm = llm
        self.tracer = tracer

        self._ensure_schema()

    def _ensure_schema(self) -> None:
        if self.w.collections.exists(CLASS_NAME):
            return

        self.w.collections.create(
            name=CLASS_NAME,
            description="Stores all known aliases for story entities",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            inverted_index_config=Configure.inverted_index(index_property_length=True),
            properties=[
                wvc.config.Property(
                    name="alias_text", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(
                    name="entity_id", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(
                    name="entity_type", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(
                    name="canonical", data_type=wvc.config.DataType.BOOL
                ),
                wvc.config.Property(name="chapter", data_type=wvc.config.DataType.INT),
                wvc.config.Property(
                    name="fragment_id", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(name="snippet", data_type=wvc.config.DataType.TEXT),
            ],
        )
        logger.info("[IdentityService] ✅ Alias collection created")

    def resolve(
        self,
        raw_name: str,
        etype: str,
        *,
        chapter: int,
        fragment_id: str,
        snippet: str,
    ) -> ResolveResult:
        """
        Главный публичный метод.
        Возвращает:
          • entity_id (устойчивый ID для вставки в слот),
          • alias_cypher (если нужна запись в Neo4j, например, для новой сущности).
        Weaviate обновляется внутри этого метода.
        """
        aliases = self._search_alias_near(raw_name, etype)
        if aliases and aliases[0]["score"] >= HI_SIM:
            return self._fast_accept(raw_name, aliases[0])

        aliases_ctx = self._search_alias_near(f"{raw_name} {etype}", etype)
        if aliases_ctx and aliases_ctx[0]["score"] >= HI_SIM:
            return self._fast_accept(raw_name, aliases_ctx[0])

        if any(a["score"] >= LO_SIM for a in aliases_ctx):
            decision = self._llm_disambiguate(
                raw_name, aliases_ctx, chapter=chapter, snippet=snippet
            )
            if decision.action == "use":
                self._insert_alias(
                    {
                        "alias_text": decision.alias_text,
                        "entity_id": decision.entity_id,
                        "entity_type": etype,
                        "canonical": False,
                        "chapter": chapter,
                        "fragment_id": fragment_id,
                        "snippet": snippet,
                    }
                )
                return ResolveResult(entity_id=decision.entity_id)

        # ← полностью новая сущность
        entity_id = f"{etype.lower()}-{fragment_id}"
        self._insert_alias(
            {
                "alias_text": raw_name,
                "entity_id": entity_id,
                "entity_type": etype,
                "canonical": True,
                "chapter": chapter,
                "fragment_id": fragment_id,
                "snippet": snippet,
            }
        )
        alias_cypher = f"CREATE (e:{etype} {{id:'{entity_id}', name:'{raw_name}'}})"
        return ResolveResult(entity_id=entity_id, alias_cypher=alias_cypher)

    def _search_alias_near(self, query_text: str, etype: str) -> List[Dict]:
        """Топ-3 ближайших alias по cosine-дистанции."""
        if not self.embedder:
            logger.warning("No embedder configured → semantic search disabled")
            return []

        vector = self.embedder(query_text)
        alias_col = self.w.collections.get(CLASS_NAME)
        try:
            res = alias_col.query.near_vector(
                near_vector=vector,
                limit=3,
                filters=Filter.by_property("entity_type").equal(etype),
                return_metadata=MetadataQuery(distance=True),
            )
        except WeaviateQueryError as e:
            logger.error(f"Near-vector failed: {e}")
            return []

        hits: List[Dict] = []
        for obj in res.objects:
            props = obj.properties
            if obj.metadata.distance is None:
                logger.warning(f"Object {obj.id} has no distance metadata, skipping")
                continue
            props["score"] = 1.0 - obj.metadata.distance
            hits.append(props)
        return sorted(hits, key=lambda x: -x["score"])

    def _fast_accept(self, raw_name, hit):
        """Alias уже есть → просто записываем новый alias в Weaviate (если нужно)."""
        if hit["alias_text"] == raw_name:
            return ResolveResult(entity_id=hit["entity_id"])
        else:
            self._insert_alias(
                {
                    "alias_text": raw_name,
                    "entity_id": hit["entity_id"],
                    "entity_type": hit["entity_type"],
                    "canonical": False,
                    "chapter": hit.get("chapter", 0),
                    "fragment_id": hit.get("fragment_id", ""),
                    "snippet": hit.get("snippet", ""),
                }
            )
            return ResolveResult(entity_id=hit["entity_id"])

    def _llm_disambiguate(
        self, raw_name, aliases, *, chapter, snippet
    ) -> AliasDecision:
        parser = PydanticOutputParser(pydantic_object=AliasDecision)
        fmt = parser.get_format_instructions()

        prompt_tmpl = PROMPTS_ENV.get_template("verify_alias_llm.j2")
        rendered = prompt_tmpl.render(
            raw_name=raw_name,
            chapter=chapter,
            snippet=snippet,
            candidates=[
                {
                    "alias_text": a["alias_text"],
                    "canonical": a["canonical"],
                    "entity_id": a["entity_id"],
                    "score": round(a["score"], 3),
                }
                for a in aliases
            ],
        )
        chain = (
            PromptTemplate(
                template=rendered + "\n\n{format_instructions}",
                input_variables=["format_instructions"],
                partial_variables={"format_instructions": fmt},
            )
            | self.llm
            | parser
        )
        return chain.invoke({})

    def _insert_alias(self, payload: Dict[str, Any]) -> None:
        alias_col = self.w.collections.get(CLASS_NAME)
        vec = payload.get("vector") or (
            self.embedder(payload["alias_text"]) if self.embedder else None
        )
        alias_col.data.insert(properties=payload, vector=vec)
        logger.info(f"[IdentityService] ➕ alias '{payload['alias_text']}' inserted")
