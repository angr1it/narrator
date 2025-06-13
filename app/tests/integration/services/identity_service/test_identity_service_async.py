"""Async IdentityService integration tests.

These tests run against a real Weaviate instance and OpenAI embeddings to
ensure that the asynchronous wrappers of :class:`IdentityService` behave the
same as the synchronous API. They insert an alias object and verify that it is
properly persisted when ``commit_aliases`` is called.
"""

import pytest
import pytest_asyncio
from uuid import uuid4

pytestmark = pytest.mark.integration

from weaviate.collections.classes.data import DataObject
from services.identity_service import (
    IdentityService,
    get_identity_service_sync,
    AliasTask,
)


@pytest.fixture(scope="session", autouse=True)
async def prepare_data(wclient, openai_embedder, clean_alias_collection):
    service = get_identity_service_sync(wclient=wclient, embedder=openai_embedder)
    await service.startup()
    alias_col = service._w.collections.get("Alias")

    await service._run_sync(
        alias_col.data.insert_many,
        [
            DataObject(
                properties={
                    "alias_text": "Arthur",
                    "entity_id": "ent1",
                    "entity_type": "CHARACTER",
                    "canonical": True,
                },
                vector=openai_embedder("Arthur"),
            )
        ],
    )

    # confirm that the object was inserted to make sure the test setup is valid
    results = alias_col.query.fetch_objects()
    assert any(obj.properties["alias_text"] == "Arthur" for obj in results.objects)


@pytest_asyncio.fixture
async def service(wclient, openai_embedder):
    svc = get_identity_service_sync(wclient=wclient, embedder=openai_embedder)
    await svc.startup()
    return svc


@pytest.mark.asyncio
async def test_commit_aliases_inserts(service: IdentityService):
    task = AliasTask(
        cypher_template_id="add_alias",
        render_slots={},
        entity_id="ent1",
        alias_text="Art",
        entity_type="CHARACTER",
        chapter=1,
        chunk_id="c1",
        snippet="Art is brave",
    )
    cyphers = await service.commit_aliases([task])
    assert not cyphers

    alias_col = service._w.collections.get("Alias")
    results = alias_col.query.fetch_objects()
    assert any(obj.properties["alias_text"] == "Art" for obj in results.objects)

    alias_col = service._w.collections.get("Alias")
    results = alias_col.query.fetch_objects()
    assert any(obj.properties["alias_text"] == "Art" for obj in results.objects)
