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


def test_render_augment_simple(jinja_env):
    """Augment mode should render the provided template."""
    jinja_env.loader.mapping["aug.j2"] = (
        "MATCH (c:Character {id: '{{ character }}'}) RETURN c"
    )
    tpl = CypherTemplateBase(
        name="t",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        augment_cypher="aug.j2",
        return_map={"c": "Character"},
    )
    cypher = tpl.render(
        {"character": "char1"}, chunk_id="cid", mode=TemplateRenderMode.AUGMENT
    )
    assert "MATCH" in cypher and "char1" in cypher


def test_validate_augment_requires_template():
    """Validation should fail if augment_cypher is missing when supported."""
    tpl = CypherTemplateBase(
        name="t",
        title="t",
        description="d",
        slots={},
        supports_augment=True,
        return_map={},
    )
    with pytest.raises(ValueError):
        tpl.validate_augment()
