"""Comprehensive TemplateService integration tests.

The tests in this module use a real Weaviate instance and OpenAI embeddings to
exercise the full CRUD and semantic search behaviour of
:class:`TemplateService`.  They serve as a smoke test for the template import
utility and search quality.
"""

import os
import openai
import pytest
from uuid import uuid4

pytestmark = pytest.mark.integration

from services.templates import TemplateService
from templates.imports import import_templates
from templates.base import base_templates


MODEL_NAME = "text-embedding-3-small"


def openai_embedder(text: str) -> list[float]:
    """Real call to OpenAI embeddings."""
    response = openai.embeddings.create(
        input=text, model=MODEL_NAME, user="template-tests"
    )
    return response.data[0].embedding


@pytest.fixture(scope="session")
def test_collection_name() -> str:
    """Generate a unique Weaviate collection name for tests."""
    return f"TplInt_{uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def template_service(weaviate_client, test_collection_name) -> TemplateService:
    if weaviate_client.collections.exists(test_collection_name):
        weaviate_client.collections.delete(test_collection_name)

    svc = TemplateService(
        weaviate_client=weaviate_client,
        embedder=openai_embedder,
        class_name=test_collection_name,
    )
    yield svc
    weaviate_client.collections.delete(test_collection_name)


@pytest.fixture(scope="session", autouse=True)
def load_base_templates(template_service: TemplateService):
    """Import base templates into the test collection before running tests."""
    import_templates(template_service, base_templates)
    yield


def test_templates_present(template_service: TemplateService):
    """Every `id` from base_templates should be retrievable via `get()`."""
    for tpl_dict in base_templates:
        tpl_name = tpl_dict["name"]
        fetched = template_service.get_by_name(tpl_name)
        assert fetched.name == tpl_name
        assert fetched.title == tpl_dict["title"]


def test_top_k_returns_relevant(template_service: TemplateService):
    """A semantic query for 'bravery' should rank the trait attribution template in top‑5."""
    results = template_service.top_k("unexpected bravery", k=5)
    names = [t.name for t in results]
    assert "trait_attribution_v1" in names


@pytest.mark.parametrize(
    "query,expected_name",
    [
        ("character joins a faction", "membership_change_v1"),
        ("character feels hate", "emotion_state_v1"),
    ],
)
def test_semantic_search_examples(
    template_service: TemplateService, query: str, expected_name: str
):
    """Parametrised smoke‑test for semantic search across two queries."""
    matches = template_service.top_k(query, k=3)
    assert any(t.name == expected_name for t in matches)
