"""Async TemplateService integration tests.

These tests verify that the asynchronous helper methods of
:class:`TemplateService` provide the same behaviour as the synchronous
operations when working with a real Weaviate and OpenAI embedder.
"""

import os
import pytest
import openai
from uuid import uuid4

pytestmark = pytest.mark.integration

from services.templates import TemplateService, CypherTemplateBase
from services.templates.service import get_weaviate_client
from templates.imports import import_templates
from templates.base import base_templates


OPENAI_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "text-embedding-3-small"


def openai_embedder(text: str) -> list[float]:
    response = openai.embeddings.create(
        input=text, model=MODEL_NAME, user="template-tests"
    )
    return response.data[0].embedding


@pytest.fixture(scope="session")
def wclient():
    openai.api_key = OPENAI_KEY
    client = get_weaviate_client()
    yield client
    client.close()


@pytest.fixture
def collection_name():
    return f"TplAsync_{uuid4().hex[:8]}"


@pytest.fixture
def service(wclient, collection_name):
    if wclient.collections.exists(collection_name):
        wclient.collections.delete(collection_name)

    wclient.collections.create(
        name=collection_name,
        vectorizer_config=None,
        properties=[],
    )

    svc = TemplateService(wclient, embedder=openai_embedder)
    svc.CLASS_NAME = collection_name
    yield svc
    wclient.collections.delete(collection_name)


@pytest.mark.asyncio
async def test_async_crud(service: TemplateService):
    tpl = CypherTemplateBase(
        name="a1", title="t", description="d", slots={}, cypher="c.j2"
    )
    saved = await service.upsert_async(tpl)
    fetched = await service.get_async(saved.id)
    assert fetched.name == "a1"
    fetched_by_name = await service.get_by_name_async("a1")
    assert fetched_by_name.id == saved.id


@pytest.mark.asyncio
async def test_async_search(service: TemplateService):
    import_templates(service, base_templates)
    hits = await service.top_k_async("bravery", k=5)
    assert hits
