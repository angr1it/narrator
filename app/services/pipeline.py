from __future__ import annotations

from typing import List, Dict, Any
from uuid import uuid4

from schemas.stage import StageEnum
from schemas.slots import SlotFill
from schemas.cypher import CypherTemplate
from services.graph_proxy import GraphProxy
from services.slot_filler import SlotFiller
from services.template_renderer import TemplateRenderer
from services.templates import TemplateService
from services.identity_service import IdentityService
from services.raptor_index import FlatRaptorIndex


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
        self._create_chunk(chunk_id, text, chapter, stage, tags or [])

        templates = self.template_service.top_k(text, k=self.top_k)
        triple_texts: List[str] = []

        for tpl in templates:
            await self._process_template(
                tpl,
                text,
                chapter,
                stage,
                chunk_id,
                triple_texts,
            )

        triple_str = " \n".join(triple_texts)
        raptor_id = self.raptor_index.insert_chunk(text, triple_str)
        self.graph_proxy.run_query(
            "MATCH (c:Chunk {id:$cid}) SET c.raptor_node_id=$rid",
            {"cid": chunk_id, "rid": raptor_id},
        )
        return {"chunk_id": chunk_id, "raptor_node_id": raptor_id}

    async def _process_template(
        self,
        template: CypherTemplate,
        text: str,
        chapter: int,
        stage: StageEnum,
        chunk_id: str,
        triple_texts: List[str],
    ) -> None:
        """Fill slots for a template and commit its Cypher.

        The method handles alias resolution, template rendering and
        Cypher execution. It appends the template's ``triple_text`` to the
        provided ``triple_texts`` list for later Raptor processing.
        """
        fills = self.slot_filler.fill_slots(template, text)
        if not fills:
            return
        fill = fills[0]

        resolve = await self.identity_service.resolve_bulk(
            fill.slots,
            chapter=chapter,
            chunk_id=chunk_id,
            snippet=text,
        )

        alias_tasks = resolve.alias_tasks
        alias_cyphers = await self.identity_service.commit_aliases(alias_tasks)

        slot_fill = SlotFill(
            template_id=str(template.id),
            slots=resolve.mapped_slots,
            details="",
        )
        meta = {
            "chunk_id": chunk_id,
            "chapter": chapter,
            "draft_stage": stage.name,
            "description": template.description,
            "confidence": template.default_confidence,
        }
        render = self.template_renderer.render(template, slot_fill, meta)

        batch = alias_cyphers + [render.content_cypher]
        self.graph_proxy.run_queries(batch)
        triple_texts.append(render.triple_text)

    def _create_chunk(
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
        self.graph_proxy.run_query(
            cypher,
            {
                "cid": chunk_id,
                "text": text,
                "ch": chapter,
                "st": stage.name,
                "tags": tags,
            },
        )
