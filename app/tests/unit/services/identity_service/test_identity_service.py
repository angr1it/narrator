"""Unit tests for IdentityService internal helpers.

These tests focus on startup behaviour, LLM disambiguation logic and alias
commit handling without relying on external services.
"""

import pytest
from services.identity_service import (
    IdentityService,
    AliasTask,
    LLMDecision,
    _render_alias_cypher,
    get_identity_service_sync,
)
from schemas.cypher import SlotDefinition
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.callbacks.base import BaseCallbackHandler


class MyFakeLLM(FakeListLLM):
    model_config = {"extra": "allow"}

    def __init__(self, responses):
        super().__init__(responses=responses)
        self._last_prompt = None
        self._calls = 0
        self._last_run_manager = None

    def _call(self, prompt, stop=None, run_manager=None, **kwargs):
        self._last_prompt = prompt
        self._last_run_manager = run_manager
        self._calls += 1
        return super()._call(prompt, stop=stop, run_manager=run_manager, **kwargs)

    async def _acall(self, prompt, stop=None, run_manager=None, **kwargs):
        self._last_prompt = prompt
        self._last_run_manager = run_manager
        self._calls += 1
        return await super()._acall(
            prompt, stop=stop, run_manager=run_manager, **kwargs
        )

    def get_prompt(self):
        return self._last_prompt

    def get_run_manager(self):
        return self._last_run_manager

    @property
    def calls(self):
        return self._calls


class DummyHandler(BaseCallbackHandler):
    pass


class DummyService(IdentityService):
    def __init__(self):
        class _C:
            collections = None

        super().__init__(
            weaviate_sync_client=_C(),
            embedder=lambda x: [0.0],
            llm=lambda x, y: {},
        )
        self.logged = []

    async def _upsert_alias(self, task: AliasTask) -> None:  # type: ignore[override]
        self.logged.append(task)


@pytest.mark.asyncio
async def test_commit_aliases_filters_add_alias():
    """Only tasks with a known template ID are executed."""
    svc = DummyService()
    tasks = [
        AliasTask(
            cypher_template_id="add_alias",
            render_slots={},
            entity_id="e1",
            alias_text="Alex",
            entity_type="CHARACTER",
            chapter=1,
            chunk_id="c1",
            snippet="txt",
            details=None,
        ),
        AliasTask(
            cypher_template_id="create_entity_with_alias",
            render_slots={},
            entity_id="e2",
            alias_text="Boris",
            entity_type="CHARACTER",
            chapter=1,
            chunk_id="c1",
            snippet="txt",
            details=None,
        ),
    ]
    cyphers = await svc.commit_aliases(tasks)
    assert len(svc.logged) == 2
    assert cyphers == ["CREATE (e:CHARACTER {id:'e2', name:'Boris', details:'None'})"]


def test_render_alias_cypher_includes_details():
    """_render_alias_cypher must include the details text."""
    task = AliasTask(
        cypher_template_id="create_entity_with_alias",
        render_slots={},
        entity_id="e3",
        alias_text="C",
        entity_type="CHARACTER",
        chapter=1,
        chunk_id="c1",
        snippet="txt",
        details="why",
    )
    cypher = _render_alias_cypher(task)
    assert "details:'why'" in cypher


class DummyClient:
    def __init__(self, exists: bool = False):
        self.created = None

        class CollMgr:
            def list_all(self_inner):
                return [type("C", (), {"name": "Alias"})] if exists else []

            def create(self_inner, **kwargs):
                self.created = kwargs

        self.collections = CollMgr()


class StartupService(IdentityService):
    def __init__(self, client: DummyClient):
        super().__init__(
            weaviate_sync_client=client,
            embedder=lambda x: [0.0],
            llm=lambda *a, **k: {},
        )


@pytest.mark.asyncio
async def test_startup_skips_if_exists():
    """Collection creation is skipped when it already exists."""
    client = DummyClient(exists=True)
    svc = StartupService(client)
    await svc.startup()
    assert client.created is None


def test_llm_disambiguate_calls_llm():
    """_llm_disambiguate_sync should parse LLM JSON response."""
    fake_llm = MyFakeLLM(
        [
            '{"action": "use", "entity_id": "e1", "alias_text": "n", "canonical": false, "details": "ok"}'
        ]
    )

    svc = IdentityService(
        weaviate_sync_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm=fake_llm,
        callback_handler=DummyHandler(),
    )

    decision = svc._llm_disambiguate_sync("n", [], 1, "t")
    assert decision.entity_id == "e1"
    assert decision.canonical is False
    assert decision.details == "ok"
    assert "n" in fake_llm.get_prompt()


@pytest.mark.asyncio
async def test_startup_creates_collection():
    """Startup should create the alias collection and required properties."""
    client = DummyClient()
    svc = StartupService(client)
    await svc.startup()
    assert client.created is not None
    props = client.created["properties"]
    assert any(p.name == "alias_text" for p in props)


def test_llm_disambiguate_callable_error():
    """Callable without LLM interface should raise an error."""

    class LLMObj:
        def __call__(self, *a, **kw):
            return LLMDecision(action="use", entity_id="e2", alias_text="n")

    svc = IdentityService(
        weaviate_sync_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm=LLMObj(),
    )
    with pytest.raises(Exception):
        svc._llm_disambiguate_sync("n", [], 1, "t")


def test_llm_disambiguate_invalid_type():
    """Non LLMDecision result should raise ValueError."""
    svc = IdentityService(
        weaviate_sync_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm=lambda *a, **k: 42,
    )
    with pytest.raises(ValueError):
        svc._llm_disambiguate_sync("n", [], 1, "t")


@pytest.mark.asyncio
async def test_llm_disambiguate_async():
    """Asynchronous disambiguation uses the async LLM API."""
    fake_llm = MyFakeLLM(
        [
            '{"action": "use", "entity_id": "e1", "alias_text": "A", "canonical": false, "details": "ok"}'
        ]
    )
    svc = IdentityService(
        weaviate_sync_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm=fake_llm,
    )
    res = await svc._llm_disambiguate(
        raw_name="A",
        aliases=[{"alias_text": "A", "entity_id": "e1", "score": 0.8}],
        chapter=2,
        snippet="txt",
    )
    assert res.action == "use"
    assert res.entity_id == "e1"
    assert res.details == "ok"
    assert "A" in fake_llm.get_prompt()


@pytest.mark.asyncio
async def test_commit_aliases_empty():
    """No tasks means no cypher and no alias updates."""
    svc = DummyService()
    result = await svc.commit_aliases([])
    assert result == []
    assert not svc.logged


@pytest.mark.asyncio
async def test_run_sync_executes_function():
    """_run_sync should offload function execution to a thread."""
    svc = DummyService()

    def add(a, b):
        return a + b

    result = await svc._run_sync(add, 2, 3)
    assert result == 5


@pytest.mark.asyncio
async def test_commit_aliases_skips_invalid_values():
    """Invalid alias texts should not be inserted."""
    svc = DummyService()
    tasks = [
        AliasTask(
            cypher_template_id="create_entity_with_alias",
            render_slots={},
            entity_id="e5",
            alias_text="he",
            entity_type="CHARACTER",
            chapter=1,
            chunk_id="c1",
            snippet="he moved",
            details=None,
        ),
        AliasTask(
            cypher_template_id="create_entity_with_alias",
            render_slots={},
            entity_id="e6",
            alias_text="to go with her",
            entity_type="GOAL",
            chapter=1,
            chunk_id="c2",
            snippet="agrees to go with her",
            details=None,
        ),
    ]

    cyphers = await svc.commit_aliases(tasks)
    assert cyphers == []
    assert not svc.logged


def test_resolve_bulk_uses_slot_defs():
    """Only entity-ref slots produce alias tasks during bulk resolve."""

    class LocalService(DummyService):
        def _nearest_alias_sync(self, *a, **k):
            return []

    svc = LocalService()
    slot_defs = {
        "character": SlotDefinition(
            name="character", type="STRING", is_entity_ref=True
        ),
        "summary": SlotDefinition(name="summary", type="STRING", is_entity_ref=False),
    }
    res = svc._resolve_bulk_sync(
        {"character": "John", "summary": "test"},
        slot_defs,
        chapter=1,
        chunk_id="c1",
        snippet="t",
    )
    assert "summary" in res.mapped_slots
    assert any(t.alias_text == "John" for t in res.alias_tasks)
    assert not any(t.alias_text == "test" for t in res.alias_tasks)
    assert res.alias_map[res.mapped_slots["character"]] == "John"


@pytest.mark.asyncio
async def test_resolve_bulk_maps_character_slots():
    """Slots 'character_a' and 'character_b' should map to new IDs."""

    class LocalService(DummyService):
        def _nearest_alias_sync(self, *a, **k):
            return []

    svc = LocalService()
    slot_defs = {
        "character_a": SlotDefinition(
            name="character_a",
            type="STRING",
            is_entity_ref=True,
            entity_type="CHARACTER",
        ),
        "character_b": SlotDefinition(
            name="character_b",
            type="STRING",
            is_entity_ref=True,
            entity_type="CHARACTER",
        ),
    }
    res = svc._resolve_bulk_sync(
        {"character_a": "Lyra", "character_b": "Luthar"},
        slot_defs,
        chapter=1,
        chunk_id="c1",
        snippet="t",
    )
    assert res.mapped_slots["character_a"].startswith("character-")
    assert res.mapped_slots["character_b"].startswith("character-")
    assert len(res.alias_tasks) == 2
    assert res.alias_map[res.mapped_slots["character_a"]] == "Lyra"
    assert res.alias_map[res.mapped_slots["character_b"]] == "Luthar"


def test_resolve_bulk_respects_entity_type():
    """Slot definitions may set entity_type explicitly."""

    class LocalService(DummyService):
        def _nearest_alias_sync(self, *a, **k):
            return []

    svc = LocalService()
    slot_defs = {
        "place": SlotDefinition(
            name="place",
            type="STRING",
            is_entity_ref=True,
            entity_type="LOCATION",
        )
    }
    res = svc._resolve_bulk_sync(
        {"place": "Paris"},
        slot_defs,
        chapter=1,
        chunk_id="c1",
        snippet="t",
    )
    assert res.mapped_slots["place"].startswith("location-")
    assert res.alias_map[res.mapped_slots["place"]] == "Paris"


def test_llm_disambiguate_skip_action():
    """_llm_disambiguate_sync should handle 'skip' responses."""

    fake_llm = MyFakeLLM(['{"action": "skip", "details": "not a name"}'])

    svc = IdentityService(
        weaviate_sync_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm=fake_llm,
    )

    decision = svc._llm_disambiguate_sync("it", [], 1, "it is here")
    assert decision.action == "skip"
    assert decision.details == "not a name"


def test_resolve_single_skip_action():
    """When LLM returns 'skip', the raw value is kept and no task is created."""

    class LocalService(DummyService):
        def _nearest_alias_sync(self, *a, **k):
            return [{"alias_text": "he", "entity_id": "e1", "score": 0.5}]

        def _llm_disambiguate_sync(self, *a, **k):
            return LLMDecision(action="skip", details="pronoun")

    svc = LocalService()
    res = svc._resolve_single_sync(
        raw_name="he",
        entity_type="CHARACTER",
        chapter=1,
        chunk_id="c1",
        snippet="he said",
    )
    assert res["entity_id"] == "he"
    assert res["need_task"] is False


def test_get_identity_service_sync_uses_default_llm():
    """When llm is None, a ChatOpenAI model is created."""

    svc = get_identity_service_sync(
        wclient=type("C", (), {"collections": None})(), embedder=lambda x: [0.0]
    )
    from langchain_openai import ChatOpenAI

    assert isinstance(svc._llm, ChatOpenAI)
