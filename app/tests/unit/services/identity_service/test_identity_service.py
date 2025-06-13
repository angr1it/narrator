"""Unit tests for IdentityService internal helpers.

These tests focus on startup behaviour, LLM disambiguation logic and alias
commit handling without relying on external services.
"""

import pytest
from services.identity_service import IdentityService, AliasTask, LLMDecision


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
    svc = DummyService()
    tasks = [
        AliasTask(
            cypher_template_id="add_alias",
            render_slots={},
            entity_id="e1",
            alias_text="A",
            entity_type="CHARACTER",
            chapter=1,
            chunk_id="c1",
            snippet="txt",
        ),
        AliasTask(
            cypher_template_id="create_entity_with_alias",
            render_slots={},
            entity_id="e2",
            alias_text="B",
            entity_type="CHARACTER",
            chapter=1,
            chunk_id="c1",
            snippet="txt",
        ),
    ]
    cyphers = await svc.commit_aliases(tasks)
    assert len(svc.logged) == 2
    assert cyphers == ["CREATE (e:CHARACTER {id:'e2', name:'B'})"]


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


# TODO: FIX IT
# @pytest.mark.asyncio
# async def test_startup_creates_collection():
#     client = DummyClient()
#     svc = StartupService(client)
#     await svc.startup()
#     assert client.created is not None
#     props = client.created["properties"]
#     assert any(p.name == "alias_text" for p in props)


@pytest.mark.asyncio
async def test_startup_skips_if_exists():
    client = DummyClient(exists=True)
    svc = StartupService(client)
    await svc.startup()
    assert client.created is None


def test_llm_disambiguate_calls_llm():
    called = {}

    def llm(raw_name, aliases, chapter, snippet):
        called["args"] = (raw_name, aliases, chapter, snippet)
        return {"action": "use", "entity_id": "e1"}

    svc = IdentityService(
        weaviate_sync_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm=llm,
        callback_handler=object(),
    )

    decision = svc._llm_disambiguate_sync("n", [], 1, "t")
    assert decision.entity_id == "e1"
    assert called["args"] == ("n", [], 1, "t")


@pytest.mark.asyncio
async def test_startup_creates_collection():
    client = DummyClient()
    svc = StartupService(client)
    await svc.startup()
    assert client.created is not None
    props = client.created["properties"]
    assert any(p.name == "alias_text" for p in props)


def test_llm_disambiguate_accepts_model():
    class LLMObj:
        def __call__(self, *a, **kw):
            return LLMDecision(action="use", entity_id="e2")

    svc = IdentityService(
        weaviate_sync_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm=LLMObj(),
    )
    decision = svc._llm_disambiguate_sync("n", [], 1, "t")
    assert isinstance(decision, LLMDecision)
    assert decision.entity_id == "e2"


def test_llm_disambiguate_invalid_type():
    svc = IdentityService(
        weaviate_sync_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm=lambda *a, **k: 42,
    )
    with pytest.raises(ValueError):
        svc._llm_disambiguate_sync("n", [], 1, "t")


@pytest.mark.asyncio
async def test_commit_aliases_empty():
    svc = DummyService()
    result = await svc.commit_aliases([])
    assert result == []
    assert not svc.logged
