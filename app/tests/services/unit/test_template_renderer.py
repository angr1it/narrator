from schemas.slots import SlotFill
from services.template_renderer import TemplateRenderer


def test_render_returns_triple_and_nodes(sample_template, slot_fill, template_renderer):
    meta = {
        "chunk_id": "c1",
        "chapter": 1,
        "draft_stage": "draft",
        "description": "d",
        "confidence": 0.2,
    }
    plan = template_renderer.render(sample_template, slot_fill, meta)
    assert "MERGE" in plan.content_cypher
    assert plan.triple_text == "char1 IS_ALIVE true"
    assert plan.related_node_ids == ["char1", "true"]


def test_missing_chunk_id_raises(sample_template, slot_fill, template_renderer):
    meta = {}
    try:
        template_renderer.render(sample_template, slot_fill, meta)
    except ValueError as exc:
        assert "chunk_id" in str(exc)
    else:
        assert False, "expected ValueError"
