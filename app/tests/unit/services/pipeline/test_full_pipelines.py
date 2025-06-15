import uuid
from jinja2 import Environment, DictLoader
import pytest

from schemas.cypher import CypherTemplate, SlotDefinition, GraphRelationDescriptor
from schemas.stage import StageEnum
from services.pipeline import ExtractionPipeline, AugmentPipeline
from services.templates import TemplateService
from services.template_renderer import TemplateRenderer
from services.slot_filler import SlotFiller
from services.identity_service import IdentityService


class DummyObj:
    def __init__(self, template):
        self.uuid = template.id
        props = template.model_dump(exclude={"id"})
        self.properties = props
        self.metadata = type("M", (), {"distance": 0.1})()


class DummyQuery:
    def __init__(self, objects):
        self._objects = objects

    def near_vector(self, *, near_vector, limit, filters=None, return_metadata=None):
        return type("Res", (), {"objects": self._objects})

    def near_text(self, *, query, limit, filters=None, return_metadata=None):
        return type("Res", (), {"objects": self._objects})


class DummyCollection:
    def __init__(self, objects):
        self.query = DummyQuery(objects)


class DummyCollections:
    def __init__(self, objects):
        self._objects = objects

    def exists(self, name):
        return True

    def create(self, **kwargs):
        pass

    def get(self, name):
        return DummyCollection(self._objects)


class DummyClient:
    def __init__(self, objects):
        self.collections = DummyCollections(objects)


class FakeGraphProxy:
    def __init__(self):
        self.calls = []

    async def run_query(self, cypher, params=None, *, write=True):
        self.calls.append(cypher)
        return []

    async def run_queries(self, cyphers, params_list=None, *, write=True):
        self.calls.append(list(cyphers))
        return []


class FakeRaptor:
    def __init__(self):
        self.inserted = []

    def insert_chunk(self, text: str, triple_text: str) -> str:
        self.inserted.append((text, triple_text))
        return "rid"


@pytest.fixture
def env_extract():
    templates = {
        "t1.j2": "MERGE (a:Character {id: '{{ character }}1'}){% set related_node_ids=[character] %}",
        "t2.j2": "MERGE (a:Character {id: '{{ character }}2'}){% set related_node_ids=[character] %}",
    }
    env = Environment(loader=DictLoader(templates))
    import schemas.cypher as cypher_mod

    cypher_mod.env = env
    return env


@pytest.fixture
def env_augment():
    templates = {
        "a1.j2": "MATCH (c:Character {id:'{{ character }}'}) RETURN c",
        "a2.j2": "MATCH (c:Character {id:'{{ character }}'}) RETURN c",
    }
    env = Environment(loader=DictLoader(templates))
    import schemas.cypher as cypher_mod

    cypher_mod.env = env
    return env


def make_template(name, cypher_file, *, augment=False):
    return CypherTemplate(
        id=uuid.uuid4(),
        name=name,
        title=name,
        description="d",
        slots={
            "character": SlotDefinition(
                name="character", type="STRING", is_entity_ref=True
            )
        },
        extract_cypher=None if augment else cypher_file,
        augment_cypher=cypher_file if augment else None,
        use_base_extract=False,
        use_base_augment=False,
        graph_relation=GraphRelationDescriptor(
            predicate="REL", subject="$character", object="true"
        ),
        return_map={"c": "Character"},
    )


@pytest.mark.asyncio
async def test_extraction_pipeline_multiple_templates(monkeypatch, env_extract):
    """ExtractionPipeline should process all provided templates."""
    tpls = [make_template("t1", "t1.j2"), make_template("t2", "t2.j2")]
    objects = [DummyObj(t) for t in tpls]
    svc = TemplateService(
        weaviate_client=DummyClient(objects), embedder=lambda x: [0.0]
    )
    svc.ensure_base_templates = lambda: None
    renderer = TemplateRenderer(env_extract)
    filler = SlotFiller(llm=None)

    async def _mock(*a, **k):
        return [{"character": "A"}]

    monkeypatch.setattr(filler, "_run_phase", _mock)
    identity = IdentityService(
        weaviate_sync_client=DummyClient([]),
        embedder=lambda _: [0.0],
        llm=lambda *_: {"action": "new"},
    )
    monkeypatch.setattr(identity, "_nearest_alias_sync", lambda *a, **k: [])
    monkeypatch.setattr(identity, "_upsert_alias_sync", lambda *a, **k: None)
    graph = FakeGraphProxy()
    raptor = FakeRaptor()
    pipeline = ExtractionPipeline(
        template_service=svc,
        slot_filler=filler,
        graph_proxy=graph,
        identity_service=identity,
        template_renderer=renderer,
        raptor_index=raptor,
        top_k=2,
    )
    result = await pipeline.extract_and_save("txt", chapter=1, stage=StageEnum.outline)
    assert result["raptor_node_id"] == "rid"
    assert len([c for c in graph.calls if isinstance(c, list)]) >= 1
    assert len(graph.calls) >= 2


@pytest.mark.asyncio
async def test_augment_pipeline_multiple_templates(monkeypatch, env_augment):
    """AugmentPipeline should query all templates and aggregate rows."""
    tpls = [
        make_template("a1", "a1.j2", augment=True),
        make_template("a2", "a2.j2", augment=True),
    ]
    objects = [DummyObj(t) for t in tpls]
    svc = TemplateService(
        weaviate_client=DummyClient(objects), embedder=lambda x: [0.0]
    )
    svc.ensure_base_templates = lambda: None
    renderer = TemplateRenderer(env_augment)
    filler = SlotFiller(llm=None)

    async def _mock(*a, **k):
        return [{"character": "A"}]

    monkeypatch.setattr(filler, "_run_phase", _mock)
    identity = IdentityService(
        weaviate_sync_client=DummyClient([]),
        embedder=lambda _: [0.0],
        llm=lambda *_: {"action": "new"},
    )
    monkeypatch.setattr(identity, "_nearest_alias_sync", lambda *a, **k: [])
    monkeypatch.setattr(identity, "_upsert_alias_sync", lambda *a, **k: None)
    graph = FakeGraphProxy()
    pipeline = AugmentPipeline(
        template_service=svc,
        slot_filler=filler,
        identity_service=identity,
        template_renderer=renderer,
        graph_proxy=graph,
        top_k=2,
    )
    result = await pipeline.augment_context("txt", chapter=1)
    assert result["context"]["rows"] == []
    assert len(graph.calls) == 2
