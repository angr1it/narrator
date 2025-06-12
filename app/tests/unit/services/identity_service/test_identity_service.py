import pytest
from services.identity_service import IdentityService, AliasTask


class DummyService(IdentityService):
    def __init__(self):
        class _C:
            collections = None

        super().__init__(
            weaviate_async_client=_C(),
            embedder=lambda x: [0.0],
            llm_disambiguator=lambda x, y: {},
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
            async def list_all(self_inner):
                return [type("C", (), {"name": "Alias"})] if exists else []

            async def create(self_inner, **kwargs):
                self.created = kwargs

        self.collections = CollMgr()


class StartupService(IdentityService):
    def __init__(self, client: DummyClient):
        super().__init__(
            weaviate_async_client=client,
            embedder=lambda x: [0.0],
            llm_disambiguator=lambda *a, **k: {},
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


@pytest.mark.asyncio
async def test_llm_disambiguate_uses_handler():
    class DummyLLM:
        def __init__(self):
            self.received = None

        async def ainvoke(self, data, config=None):
            self.received = config
            return {"action": "use", "entity_id": "e1"}

    llm = DummyLLM()
    handler = object()
    svc = IdentityService(
        weaviate_async_client=type("C", (), {"collections": None})(),
        embedder=lambda x: [0.0],
        llm_disambiguator=llm,
        callback_handler=handler,
    )

    decision = await svc._llm_disambiguate("n", [], 1, "t")
    assert decision.entity_id == "e1"
    assert llm.received == {"callbacks": [handler]}
