"""Tests for the ExtractionPipeline orchestration logic.

Only lightweight dummy services are used to validate that the pipeline calls
its dependencies correctly and returns the expected plan.
"""

import pytest
from schemas.stage import StageEnum
from schemas.slots import SlotFill

from services.pipeline import ExtractionPipeline


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
        def fill_slots(self, template, text):
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
        def fill_slots(self, template, text):
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
