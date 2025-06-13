import pytest
from jinja2 import Environment, DictLoader
from uuid import uuid4

from schemas.cypher import CypherTemplate, SlotDefinition, GraphRelationDescriptor
from services.template_renderer import TemplateRenderer
from schemas.slots import SlotFill


class FakeGraphProxy:
    def __init__(self):
        self.calls: list[tuple] = []

    async def run_query(self, cypher: str, params=None, *, write=True):
        self.calls.append((cypher, params))
        return []

    async def run_queries(self, cyphers, params_list=None, *, write=True):
        self.calls.append((list(cyphers), params_list))
        return []


class FakeIdentityService:
    async def resolve_bulk(self, slots, *, chapter, chunk_id, snippet):
        from services.identity_service import BulkResolveResult

        return BulkResolveResult(mapped_slots=slots, alias_tasks=[])

    async def commit_aliases(self, alias_tasks):
        return []


class FakeRaptor:
    def __init__(self):
        self.inserted = []

    def insert_chunk(self, text: str, triple_text: str) -> str:
        self.inserted.append((text, triple_text))
        return "rn-test"


@pytest.fixture()
def jinja_env():
    templates = {
        "simple.j2": "MERGE (a:Character {id: '{{ character }}'}){% set related_node_ids=[character] %}"
    }
    env = Environment(loader=DictLoader(templates))
    import schemas.cypher as cypher_mod

    cypher_mod.env = env
    return env


@pytest.fixture()
def sample_template(jinja_env):
    return CypherTemplate(
        id=uuid4(),
        name="simple",
        version="1.0",
        title="t",
        description="d",
        slots={"character": SlotDefinition(name="character", type="STRING")},
        cypher="simple.j2",
        use_base=False,
        graph_relation=GraphRelationDescriptor(
            predicate="IS_ALIVE",
            subject="$character",
            object="true",
        ),
        return_map={"uid": "a"},
    )


@pytest.fixture()
def template_renderer(jinja_env):
    return TemplateRenderer(jinja_env)


@pytest.fixture()
def slot_fill(sample_template):
    return SlotFill(
        template_id=str(sample_template.id),
        slots={"character": "char1"},
        details="",
    )


@pytest.fixture()
def graph_proxy():
    return FakeGraphProxy()


@pytest.fixture()
def identity_service():
    return FakeIdentityService()


@pytest.fixture()
def raptor_index():
    return FakeRaptor()
