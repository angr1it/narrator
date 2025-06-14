import uuid
import pytest
from jinja2 import Environment, DictLoader

from schemas.cypher import (
    CypherTemplateBase,
    SlotDefinition,
    TemplateRenderMode,
    env as global_env,
)


@pytest.fixture()
def jinja_env():
    mapping = {}
    env = Environment(loader=DictLoader(mapping))
    global_env.loader = env.loader
    return env


def test_render_augment_with_base(jinja_env):
    """Augment mode should include the base wrapper when enabled."""
    jinja_env.loader.mapping["chunk_mentions.j2"] = "BASE {% include template_body %}"
    jinja_env.loader.mapping["aug.j2"] = (
        "MATCH (c:Character {id: '{{ character }}'}) RETURN c"
    )
    tpl = CypherTemplateBase(
        name="t",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        augment_cypher="aug.j2",
        use_base_augment=True,
        return_map={"c": "Character"},
    )
    cypher = tpl.render(
        {"character": "char1"}, chunk_id="cid", mode=TemplateRenderMode.AUGMENT
    )
    assert "BASE" in cypher
    assert "char1" in cypher


def test_validate_augment_flags():
    """Validation should fail if ``use_base_augment`` is True without template."""
    tpl = CypherTemplateBase(
        name="t",
        title="t",
        description="d",
        slots={},
        use_base_augment=True,
        return_map={},
    )
    try:
        tpl.validate_augment()
    except ValueError as exc:
        assert "use_base_augment" in str(exc)
    else:
        assert False, "expected ValueError"
