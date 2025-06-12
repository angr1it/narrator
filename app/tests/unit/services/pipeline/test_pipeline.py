import os
import pytest
from schemas.stage import StageEnum

os.environ.setdefault("OPENAI_API_KEY", "x")
os.environ.setdefault("NEO4J_URI", "bolt://example.com")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "pass")
os.environ.setdefault("NEO4J_DB", "neo4j")
os.environ.setdefault("WEAVIATE_URL", "http://localhost")
os.environ.setdefault("WEAVIATE_API_KEY", "x")
os.environ.setdefault("WEAVIATE_INDEX", "idx")
os.environ.setdefault("WEAVIATE_CLASS_NAME", "cls")
os.environ.setdefault("AUTH_TOKEN", "x")

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
        def top_k(self, text, k=3):
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
