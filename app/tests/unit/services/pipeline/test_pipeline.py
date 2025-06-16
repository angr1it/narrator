"""Tests for the ExtractionPipeline orchestration logic.

Only lightweight dummy services are used to validate that the pipeline calls
its dependencies correctly and returns the expected plan.
"""

import pytest
from schemas.stage import StageEnum
from schemas.slots import SlotFill

from services.pipeline import ExtractionPipeline, AugmentPipeline
from services.template_renderer import TemplateRenderer
from schemas.cypher import (
    CypherTemplate,
    SlotDefinition,
    GraphRelationDescriptor,
    TemplateRenderMode,
)
from uuid import uuid4
from pydantic import BaseModel, ValidationError


@pytest.mark.asyncio
async def test_pipeline_simple(
    sample_template,
    template_renderer,
    slot_fill,
    graph_proxy,
    identity_service,
    raptor_index,
    jinja_env,
):
    class FakeTemplateService:
        async def top_k_async(self, text, k=3):
            return [sample_template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=template_renderer,
        raptor_index=raptor_index,
    )

    result = await pipeline.extract_and_save(
        "hello", chapter=1, stage=StageEnum.outline
    )
    assert result["raptor_node_id"] == "rn-test"
    assert raptor_index.inserted[0][0] == "hello"
    merged = []
    for call in graph_proxy.calls:
        if isinstance(call[0], list):
            merged.extend(call[0])
    assert any("MERGE" in c for c in merged)
    update = [
        c for c, _ in graph_proxy.calls if isinstance(c, str) and "raptor_node_id" in c
    ]
    assert update, "raptor id update not executed"


@pytest.mark.asyncio
async def test_pipeline_returns_details(
    sample_template,
    template_renderer,
    graph_proxy,
    identity_service,
    raptor_index,
):
    class FakeTemplateService:
        async def top_k_async(self, text, k=3):
            return [sample_template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [
                SlotFill(
                    template_id=str(template.id),
                    slots={"character": "c"},
                    details="why",
                )
            ]

    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=template_renderer,
        raptor_index=raptor_index,
    )

    result = await pipeline.extract_and_save("txt", chapter=1)
    assert result["relationships"][0]["details"] == "why"


@pytest.mark.asyncio
async def test_pipeline_converts_raptor_id_to_str(
    sample_template,
    template_renderer,
    graph_proxy,
    identity_service,
    jinja_env,
):
    class NonStrId:
        def __str__(self) -> str:
            return "rn-test"

    class FakeRaptor:
        def insert_chunk(self, text: str, triple_text: str) -> NonStrId:
            return NonStrId()

    class FakeTemplateService:
        async def top_k_async(self, text, k=3):
            return [sample_template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [
                SlotFill(
                    template_id=str(template.id), slots={"character": "c"}, details=""
                )
            ]

    raptor = FakeRaptor()
    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=template_renderer,
        raptor_index=raptor,
    )

    await pipeline.extract_and_save("txt", chapter=1)
    update = [p for c, p in graph_proxy.calls if "raptor_node_id" in c][0]
    assert isinstance(update["rid"], str)


@pytest.mark.asyncio
async def test_pipeline_splits_cypher_at_with_star(
    graph_proxy, identity_service, raptor_index, jinja_env
):
    """Queries containing ``WITH *`` should run as two statements."""
    jinja_env.loader.mapping["chunk_mentions.j2"] = (
        "{% include template_body %}\nWITH *\n"
        "MATCH (chunk:Chunk {id: '{{ chunk_id }}'})\n"
        "  MATCH (x1 {id: '{{ related_node_ids[0] }}'})\n"
        "  MERGE (chunk)-[:MENTIONS]->(x1)"
    )
    jinja_env.loader.mapping["full.j2"] = (
        "MERGE (c:Character {id: '{{ character }}'})\n"
        "MERGE (t:Trait {id: '{{ trait }}'})\n"
        "MERGE (c)-[:HAS_TRAIT]->(t)\n"
        "{% set related_node_ids=[character, trait] %}"
    )
    template = CypherTemplate(
        id=uuid4(),
        name="full",
        title="t",
        description="d",
        slots={
            "character": SlotDefinition(name="character", type="STRING"),
            "trait": SlotDefinition(name="trait", type="STRING"),
        },
        extract_cypher="full.j2",
        use_base_extract=True,
        graph_relation=GraphRelationDescriptor(
            predicate="HAS", subject="$character", object="$trait"
        ),
        return_map={"c": "Character"},
    )
    slot_fill = SlotFill(
        template_id=str(template.id),
        slots={"character": "c", "trait": "t"},
        details="",
    )

    class FakeTemplateService:
        async def top_k_async(self, text, k=3):
            return [template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    pipeline = ExtractionPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        graph_proxy=graph_proxy,
        identity_service=identity_service,
        template_renderer=TemplateRenderer(jinja_env),
        raptor_index=raptor_index,
    )

    await pipeline.extract_and_save("txt", chapter=1)

    batch = [c for c in graph_proxy.calls if isinstance(c[0], list)][0][0]
    assert len(batch) == 2
    assert batch[0].startswith("MERGE")
    assert batch[1].startswith("MATCH")


@pytest.mark.asyncio
async def test_augment_pipeline_splits_cypher_at_with_star(
    graph_proxy, identity_service, jinja_env
):
    """Augment queries containing ``WITH *`` should run as two statements."""
    jinja_env.loader.mapping["aug.j2"] = (
        "MATCH (c:Character {id: '{{ character }}'}) WITH * MATCH (c) RETURN c"
    )

    template = CypherTemplate(
        id=uuid4(),
        name="aug",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        augment_cypher="aug.j2",
        graph_relation=GraphRelationDescriptor(
            predicate="REL", subject="$character", object="true"
        ),
        return_map={"c": "Character"},
    )
    slot_fill = SlotFill(
        template_id=str(template.id),
        slots={"character": "c"},
        details="",
    )

    class FakeTemplateService:
        async def top_k_async(self, text, k=3, mode=TemplateRenderMode.AUGMENT):
            return [template]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            return [slot_fill]

    pipeline = AugmentPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        identity_service=identity_service,
        template_renderer=TemplateRenderer(jinja_env),
        graph_proxy=graph_proxy,
    )

    await pipeline.augment_context("txt", chapter=1)

    batch = [c for c in graph_proxy.calls if isinstance(c[0], list)][0][0]
    assert len(batch) == 2
    assert batch[0].startswith("MATCH")
    assert batch[1].startswith("MATCH")


@pytest.mark.asyncio
async def test_augment_pipeline_skips_failed_template(
    graph_proxy, identity_service, jinja_env
):
    """Pipeline should continue if one template fails to fill slots."""
    jinja_env.loader.mapping.update(
        {
            "bad.j2": "MATCH (c:Character {id: '{{ character }}'}) RETURN c",
            "ok.j2": "MATCH (c:Character {id: '{{ character }}'}) RETURN c",
        }
    )
    bad_tpl = CypherTemplate(
        id=uuid4(),
        name="bad",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        augment_cypher="bad.j2",
        graph_relation=GraphRelationDescriptor(
            predicate="REL", subject="$character", object="true"
        ),
        return_map={"c": "Character"},
    )
    ok_tpl = CypherTemplate(
        id=uuid4(),
        name="ok",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        augment_cypher="ok.j2",
        graph_relation=GraphRelationDescriptor(
            predicate="REL", subject="$character", object="true"
        ),
        return_map={"c": "Character"},
    )
    slot_fill = SlotFill(
        template_id=str(ok_tpl.id),
        slots={"character": "c"},
        details="",
    )

    class FakeTemplateService:
        async def top_k_async(self, text, k=3, mode=TemplateRenderMode.AUGMENT):
            return [bad_tpl, ok_tpl]

    class FakeSlotFiller:
        async def fill_slots(self, template, text):
            if template is bad_tpl:

                class M(BaseModel):
                    a: str

                try:
                    M()
                except ValidationError as e:
                    raise e
            return [slot_fill]

    pipeline = AugmentPipeline(
        template_service=FakeTemplateService(),
        slot_filler=FakeSlotFiller(),
        identity_service=identity_service,
        template_renderer=TemplateRenderer(jinja_env),
        graph_proxy=graph_proxy,
    )

    await pipeline.augment_context("txt", chapter=1)

    assert len(graph_proxy.calls) == 1
    assert graph_proxy.calls[0][0].startswith("MATCH")
