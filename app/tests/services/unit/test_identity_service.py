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
