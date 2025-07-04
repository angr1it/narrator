"""Real OpenAI embedding tests for TemplateService.

These slower tests ensure end‑to‑end integration between OpenAI embeddings and
Weaviate when importing the base templates.  They run only when integration
tests are enabled and require network access to OpenAI.
"""

import time

import pytest
from services.templates import TemplateService

pytestmark = pytest.mark.integration

from templates.base import base_templates
from templates.imports import import_templates


def narrative_samples():
    """(query, expected slug) pairs close to production usage."""
    return [
        # (
        #     "During the siege Arya displayed unexpected bravery saving her comrades.",
        #     "trait_attribution_v1",
        # ),
        (
            "Sir Lancel renounced his vows and pledged allegiance to the rebel lord.",
            "membership_change_v1",
        ),
        (
            "Jon finally accepted Sansa as his sister and ally against their enemies.",
            "character_relation_v1",
        ),
    ]


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


# ----------  TESTS  ----------------------------------------------------------
def test_bulk_import_and_semantic_search(service):
    # -------- 1) bulk import
    import_templates(service, base_templates)

    # небольшая пауза, чтобы HNSW успел проиндексировать
    time.sleep(1.0)

    # -------- 2) direct retrieval sanity
    for tpl in base_templates:
        obj = service.get_by_name(tpl["name"])
        assert obj.title == tpl["title"]

    # -------- 3) semantic search with real embeddings
    for query, expected_slug in narrative_samples():
        hits = service.top_k(query, k=1)
        assert hits, f"No result for query: {query}"
        assert hits[0].name == expected_slug
