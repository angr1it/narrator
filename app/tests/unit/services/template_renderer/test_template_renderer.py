"""Tests for TemplateRenderer Jinja template rendering.

The sample template fixtures mimic the base templates to ensure slot filling and
return-map logic behave as expected when using Jinja.
"""

import pytest
from uuid import uuid4
from pathlib import Path

from schemas.cypher import CypherTemplate, SlotDefinition, GraphRelationDescriptor
from schemas.slots import SlotFill
from services.template_renderer import TemplateRenderer
from schemas.cypher import TemplateRenderMode
from jinja2 import Environment, FileSystemLoader


def test_render_returns_triple_and_nodes(sample_template, slot_fill, template_renderer):
    """Rendered Cypher should contain MERGE and triple info."""
    meta = {
        "chunk_id": "c1",
        "chapter": 1,
        "draft_stage": 1,
        "description": "d",
        "confidence": 0.2,
    }
    plan = template_renderer.render(sample_template, slot_fill, meta)
    assert "MERGE" in plan.content_cypher
    assert plan.triple_text == "char1 IS_ALIVE true"
    assert plan.related_node_ids == ["char1", "true"]
    assert plan.details == ""


def test_missing_chunk_id_raises(sample_template, slot_fill, template_renderer):
    """A missing chunk_id should raise ValueError."""
    meta = {}
    try:
        template_renderer.render(sample_template, slot_fill, meta)
    except ValueError as exc:
        assert "chunk_id" in str(exc)
    else:
        assert False, "expected ValueError"


def test_missing_return_map_raises(sample_template, slot_fill, template_renderer):
    """Renderer requires return_map to be defined."""
    template = sample_template.model_copy()
    template.return_map = {}
    meta = {"chunk_id": "c1"}
    with pytest.raises(ValueError):
        template_renderer.render(template, slot_fill, meta)


def test_use_base_includes_base(jinja_env, sample_template, slot_fill):
    """When ``use_base_extract`` is set, base template is included."""
    jinja_env.loader.mapping["chunk_mentions.j2"] = "{% include template_body %}"
    template = sample_template.model_copy()
    template.use_base_extract = True
    renderer = TemplateRenderer(jinja_env)
    meta = {"chunk_id": "c1"}
    plan = renderer.render(template, slot_fill, meta)
    assert "MERGE" in plan.content_cypher


def test_render_includes_details(jinja_env):
    """Ensure SlotFill.details is inserted via the relation meta snippet."""
    jinja_env.loader.mapping["_relation_meta.j2"] = (
        'details: "{{ details }}", description: "{{ description }}"'
    )
    jinja_env.loader.mapping["with_meta.j2"] = (
        "MERGE (a:Character {id: '{{ character }}'})\n"
        "MERGE (a)-[:REL { {% include '_relation_meta.j2' %} }]-(b)\n"
        "{% set related_node_ids=[character] %}"
    )
    template = CypherTemplate(
        id=uuid4(),
        name="with_meta",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        extract_cypher="with_meta.j2",
        use_base_extract=False,
        graph_relation=GraphRelationDescriptor(
            predicate="REL",
            subject="$character",
            object=None,
        ),
        return_map={"c": "Character"},
    )
    renderer = TemplateRenderer(jinja_env)
    fill = SlotFill(
        template_id=str(template.id),
        slots={"character": "char1"},
        details="why",
    )
    meta = {
        "chunk_id": "c1",
        "chapter": 1,
        "draft_stage": 1,
        "description": "d",
        "confidence": 0.1,
    }
    plan = renderer.render(template, fill, meta)
    assert 'details: "why"' in plan.content_cypher
    assert 'description: "d"' in plan.content_cypher
    assert plan.details == "why"


def test_no_auto_return(jinja_env):
    """Renderer does not append RETURN if template omits it."""

    jinja_env.loader.mapping["yield_end.j2"] = (
        "MERGE (a:Character {id: '{{ a }}'})\n"
        "MERGE (b:Character {id: '{{ b }}'})\n"
        "CALL apoc.create.relationship(a, 'REL', {}, b) YIELD rel\n"
        "{% set related_node_ids=[a, b] %}"
    )
    template = CypherTemplate(
        id=uuid4(),
        name="yield_end",
        title="t",
        description="d",
        slots={
            "a": SlotDefinition(name="a", type="STRING"),
            "b": SlotDefinition(name="b", type="STRING"),
        },
        extract_cypher="yield_end.j2",
        use_base_extract=False,
        graph_relation=GraphRelationDescriptor(
            predicate="REL",
            subject="$a",
            object="$b",
        ),
        return_map={"r": "rel"},
    )
    renderer = TemplateRenderer(jinja_env)
    fill = SlotFill(
        template_id=str(template.id),
        slots={"a": "c1", "b": "c2"},
        details="",
    )
    meta = {"chunk_id": "c1"}
    plan = renderer.render(template, fill, meta)

    assert not plan.content_cypher.strip().endswith("RETURN rel")


def test_relocation_augment_ignores_place_id():
    """The relocation augment template should not filter by place ID."""
    env = Environment(loader=FileSystemLoader("app/templates/cypher"))
    import schemas.cypher as cypher_mod

    cypher_mod.env = env
    renderer = TemplateRenderer(env)
    template = CypherTemplate(
        id=uuid4(),
        name="reloc_test",
        title="t",
        description="d",
        slots={
            "character": SlotDefinition(name="character", type="STRING"),
            "place": SlotDefinition(name="place", type="STRING"),
        },
        augment_cypher="relocation_aug_v1.j2",
        return_map={"c": "Character", "p": "Place"},
    )
    fill = SlotFill(
        template_id=str(template.id),
        slots={"character": "c1", "place": "p1"},
        details="",
    )
    meta = {"chunk_id": "c"}
    plan = renderer.render(template, fill, meta, mode=TemplateRenderMode.AUGMENT)
    assert "Place {id" not in plan.content_cypher


def test_shared_instructions_mentions_null_rule():
    """Prompt instructions should tell the model not to guess missing slots."""
    text = Path("app/core/slots/prompts/jinja/shared_instructions.j2").read_text()
    assert "null" in text.lower()
