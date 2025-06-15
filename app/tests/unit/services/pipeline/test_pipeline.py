"""Tests for the ExtractionPipeline orchestration logic.

Only lightweight dummy services are used to validate that the pipeline calls
its dependencies correctly and returns the expected plan.
"""

import pytest
from schemas.stage import StageEnum
from schemas.slots import SlotFill

from services.pipeline import ExtractionPipeline
from services.template_renderer import TemplateRenderer
from schemas.cypher import CypherTemplate, SlotDefinition, GraphRelationDescriptor
from uuid import uuid4


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
