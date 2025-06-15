from __future__ import annotations

from typing import List, Dict, Any, Tuple, Callable, Awaitable, cast
from uuid import uuid4
import inspect

from schemas.stage import StageEnum
from schemas.slots import SlotFill
from schemas.cypher import CypherTemplate, TemplateRenderMode
from services.graph_proxy import GraphProxy
from services.slot_filler import SlotFiller
from services.template_renderer import TemplateRenderer
from services.templates import TemplateService
from services.identity_service import IdentityService
from services.raptor_index import FlatRaptorIndex
from functools import lru_cache


class ExtractionPipeline:
    """Pipeline that maps raw text to graph relations tied to a ``ChunkNode``.

    The class orchestrates the following steps:

    1. **Chunk creation** – inserts ``:Chunk`` node with the incoming text.
    2. **Template search** – selects top templates using :class:`TemplateService`.
    3. **Slot filling** – extracts slot values via :class:`SlotFiller`.
    4. **Alias resolution** – resolves entity references with
       :class:`IdentityService` and stores :class:`AliasRecord` objects.
    5. **Cypher rendering** – renders domain Cypher with
       :class:`TemplateRenderer` (injecting ``chunk_id``).
    6. **Graph execution** – executes prepared Cypher batch with
       :class:`GraphProxy`.
    7. **Raptor clustering** – computes embeddings of the text and the rendered
       triples, then updates ``chunk.raptor_node_id`` using
       :class:`FlatRaptorIndex`.
    """

    def __init__(
        self,
        template_service: TemplateService,
        slot_filler: SlotFiller,
        graph_proxy: GraphProxy,
        identity_service: IdentityService,
        template_renderer: TemplateRenderer,
        raptor_index: FlatRaptorIndex,
        top_k: int = 3,
    ) -> None:
        self.template_service = template_service
        self.slot_filler = slot_filler
        self.graph_proxy = graph_proxy
        self.identity_service = identity_service
        self.template_renderer = template_renderer
        self.raptor_index = raptor_index
        self.top_k = top_k

    async def extract_and_save(
        self,
        text: str,
        chapter: int,
        stage: StageEnum = StageEnum.brainstorm,
        tags: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Run the end-to-end extraction for a single text fragment.

        Parameters
        ----------
        text:
            Raw narrative text to analyse.
        chapter:
            Numeric chapter identifier stored on the ``ChunkNode``.
        stage:
            Draft stage (brainstorm/outline/etc.).
        tags:
            Optional list of user supplied tags.

        Returns
        -------
        Dict[str, Any]
            ``{"chunk_id": ..., "raptor_node_id": ...}``
        """
        chunk_id = f"chunk-{uuid4().hex[:8]}"
        await self._create_chunk(chunk_id, text, chapter, stage, tags or [])

        templates = await self.template_service.top_k_async(text, k=self.top_k)
        triple_texts: List[str] = []
        relationships: List[Dict[str, str | None]] = []
        aliases: List[Dict[str, str]] = []

        for tpl in templates:
            rel, alias_list = await self._process_template(
                tpl,
                text,
                chapter,
                stage,
                chunk_id,
                triple_texts,
            )
            relationships.extend(rel)
            aliases.extend(alias_list)

        triple_str = " \n".join(triple_texts)
        raptor_id = self.raptor_index.insert_chunk(text, triple_str)
        await self.graph_proxy.run_query(
            "MATCH (c:Chunk {id:$cid}) SET c.raptor_node_id=$rid",
            {"cid": chunk_id, "rid": raptor_id},
        )
        return {
            "chunk_id": chunk_id,
            "raptor_node_id": raptor_id,
            "relationships": relationships,
            "aliases": aliases,
        }

    async def _process_template(
        self,
        template: CypherTemplate,
        text: str,
        chapter: int,
        stage: StageEnum,
        chunk_id: str,
        triple_texts: List[str],
    ) -> Tuple[List[Dict[str, str | None]], List[Dict[str, str]]]:
        """Fill slots for a template and persist its relationships.

        The method resolves entity aliases, renders the template and executes
        the resulting Cypher.  ``chunk_mentions.j2`` injects a ``WITH *``
        separator so that the domain MERGE statements run before ``MENTIONS``
        edges are attached to the ``Chunk``.  Neo4j still reports a
        ``MATCH after MERGE`` error when all commands are issued in a single
        statement.  To avoid this the statement is split around ``WITH *`` and
        executed as two sequential queries within one transaction.  The
        template's ``triple_text`` is collected for later insertion into the
        Raptor index.
        """
        fills = await self.slot_filler.fill_slots(template, text)
        if not fills:
            return [], []
        fill = fills[0]

        resolve = await self.identity_service.resolve_bulk(
            fill.slots,
            slot_defs=template.slots,
            chapter=chapter,
            chunk_id=chunk_id,
            snippet=text,
        )

        alias_tasks = resolve.alias_tasks
        alias_cyphers = await self.identity_service.commit_aliases(alias_tasks)
        alias_info = [
            {"alias_text": t.alias_text, "entity_id": t.entity_id} for t in alias_tasks
        ]

        slot_fill = SlotFill(
            template_id=str(template.id),
            slots=resolve.mapped_slots,
            details=fill.details,
        )
        meta = {
            "chunk_id": chunk_id,
            "chapter": chapter,
            "draft_stage": stage.name,
            "description": template.description,
            "confidence": template.default_confidence,
        }
        render = self.template_renderer.render(template, slot_fill, meta)

        cypher = render.content_cypher
        # Neo4j may reject queries that mix MERGE with MATCH even when
        # separated by ``WITH *`` inside a single statement. ``chunk_mentions.j2``
        # inserts such a separator, therefore we split the statement into two
        # parts to execute them sequentially.
        query_parts = [cypher]
        if "WITH *" in cypher:
            head, tail = cypher.split("WITH *", 1)
            query_parts = [head.strip(), tail.strip()]

        batch = alias_cyphers + query_parts
        await self.graph_proxy.run_queries(batch)
        triple_texts.append(render.triple_text)

        relations: List[Dict[str, str | None]] = []
        if template.graph_relation:

            def pick(expr: str | None) -> str | None:
                if expr and expr.startswith("$"):
                    return resolve.mapped_slots.get(expr[1:])
                return expr

            subj = pick(template.graph_relation.subject)
            obj = pick(template.graph_relation.object)
            relations.append(
                {
                    "subject": str(subj),
                    "predicate": template.graph_relation.predicate,
                    "object": str(obj) if obj is not None else None,
                    "details": fill.details,
                }
            )

        return relations, alias_info

    async def _create_chunk(
        self,
        chunk_id: str,
        text: str,
        chapter: int,
        stage: StageEnum,
        tags: List[str],
    ) -> None:
        """Insert a new ``Chunk`` node representing the raw text."""
        cypher = (
            "CREATE (c:Chunk {id:$cid, text:$text, chapter:$ch, "
            "draft_stage:$st, tags:$tags})"
        )
        await self.graph_proxy.run_query(
            cypher,
            {
                "cid": chunk_id,
                "text": text,
                "ch": chapter,
                "st": stage.name,
                "tags": tags,
            },
        )


@lru_cache(maxsize=1)
def get_extraction_pipeline() -> ExtractionPipeline:
    """Return a lazily created :class:`ExtractionPipeline`.

    The pipeline is initialised on first use and reused across requests.
    It wires together external services (Weaviate, Neo4j, OpenAI) using
    credentials from :data:`app_settings`.
    """
    from langchain_openai import ChatOpenAI

    from config import app_settings
    from config.langfuse import provide_callback_handler_with_tags
    from services.templates.service import get_template_service
    from services.template_renderer import get_template_renderer
    from services.graph_proxy import get_graph_proxy
    from services.identity_service import get_identity_service_sync
    from services.raptor_index import get_raptor_index

    llm = ChatOpenAI(api_key=app_settings.OPENAI_API_KEY, temperature=0.0)
    handler = provide_callback_handler_with_tags(tags=["SlotFiller"])
    filler = SlotFiller(llm=llm, callback_handler=handler)

    return ExtractionPipeline(
        template_service=get_template_service(),
        slot_filler=filler,
        graph_proxy=get_graph_proxy(),
        identity_service=get_identity_service_sync(),
        template_renderer=get_template_renderer(),
        raptor_index=get_raptor_index(),
    )


class AugmentPipeline:
    """Pipeline that enriches a text fragment with context from the graph."""

    def __init__(
        self,
        template_service: TemplateService,
        slot_filler: SlotFiller,
        identity_service: IdentityService,
        template_renderer: TemplateRenderer,
        graph_proxy: GraphProxy,
        *,
        summariser: (
            Callable[[List[Dict[str, Any]]], Awaitable[str] | str] | None
        ) = None,
        top_k: int = 3,
    ) -> None:
        self.template_service = template_service
        self.slot_filler = slot_filler
        self.identity_service = identity_service
        self.template_renderer = template_renderer
        self.graph_proxy = graph_proxy
        self.summariser = summariser
        self.top_k = top_k

    async def augment_context(
        self, text: str, chapter: int, tags: List[str] | None = None
    ) -> Dict[str, Any]:  # pragma: no cover - integration tested separately
        templates = await self.template_service.top_k_async(
            text, k=self.top_k, mode=TemplateRenderMode.AUGMENT
        )

        rows: List[Dict[str, Any]] = []
        for tpl in templates:
            fills = await self.slot_filler.fill_slots(tpl, text)
            for fill in fills:
                resolve = await self.identity_service.resolve_bulk(
                    fill.slots,
                    slot_defs=tpl.slots,
                    chapter=chapter,
                    chunk_id="aug",
                    snippet=text,
                )

                slot_fill = SlotFill(
                    template_id=str(tpl.id),
                    slots=resolve.mapped_slots,
                    details=fill.details,
                )
                meta = {
                    "chunk_id": "aug",
                    "chapter": chapter,
                    "description": tpl.description,
                }
                plan = self.template_renderer.render(
                    tpl, slot_fill, meta, mode=TemplateRenderMode.AUGMENT
                )
                result = await self.graph_proxy.run_query(
                    plan.content_cypher, write=False
                )
                rows.extend(result)

        summary = None
        if self.summariser:
            if inspect.iscoroutinefunction(self.summariser):
                coro = cast(
                    Callable[[List[Dict[str, Any]]], Awaitable[str]], self.summariser
                )
                summary = await coro(rows)
            else:
                fn = cast(Callable[[List[Dict[str, Any]]], str], self.summariser)
                summary = fn(rows)

        return {"context": {"rows": rows, "summary": summary}, "trace_id": ""}


@lru_cache(maxsize=1)
def get_augment_pipeline() -> AugmentPipeline:
    """Return a lazily created :class:`AugmentPipeline`."""  # pragma: no cover
    from langchain_openai import ChatOpenAI

    from config import app_settings
    from config.langfuse import provide_callback_handler_with_tags
    from services.templates.service import get_template_service
    from services.template_renderer import get_template_renderer
    from services.graph_proxy import get_graph_proxy
    from services.identity_service import get_identity_service_sync

    llm = ChatOpenAI(api_key=app_settings.OPENAI_API_KEY, temperature=0.0)
    handler = provide_callback_handler_with_tags(tags=["SlotFiller"])
    filler = SlotFiller(llm=llm, callback_handler=handler)

    return AugmentPipeline(
        template_service=get_template_service(),
        slot_filler=filler,
        identity_service=get_identity_service_sync(),
        template_renderer=get_template_renderer(),
        graph_proxy=get_graph_proxy(),
    )
