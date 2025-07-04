"""Async TemplateService integration tests.

These tests verify that the asynchronous helper methods of
:class:`TemplateService` provide the same behaviour as the synchronous
operations when working with a real Weaviate and OpenAI embedder.
"""

import pytest

pytestmark = pytest.mark.integration

from services.templates import (
    TemplateService,
    CypherTemplateBase,
)
from templates.imports import import_templates
from templates.base import base_templates


@pytest.fixture
def collection_name(temp_collection_name):
    return temp_collection_name


@pytest.fixture
def service(wclient, collection_name, openai_embedder):
    if wclient.collections.exists(collection_name):
        wclient.collections.delete(collection_name)

    svc = TemplateService(
        weaviate_client=wclient,
        embedder=openai_embedder,
        class_name=collection_name,
    )
    yield svc
    wclient.collections.delete(collection_name)


@pytest.mark.asyncio
async def test_async_crud(service: TemplateService):
    """Async CRUD operations mirror the sync implementations."""
    tpl = CypherTemplateBase(
        name="a1",
        title="t",
        description="d",
        slots={},
        extract_cypher="c.j2",
        return_map={},
    )
    saved = await service.upsert_async(tpl)
    fetched = await service.get_async(saved.id)
    assert fetched.name == "a1"
    fetched_by_name = await service.get_by_name_async("a1")
    assert fetched_by_name.id == saved.id


@pytest.mark.asyncio
async def test_async_search(service: TemplateService):
    """Async ``top_k`` search should return results."""
    import_templates(service, base_templates)
    hits = await service.top_k_async("bravery", k=5)
    assert hits
