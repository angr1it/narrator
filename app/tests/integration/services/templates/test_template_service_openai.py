"""Real OpenAI embedding tests for TemplateService.

These slower tests ensure end‑to‑end integration between OpenAI embeddings and
Weaviate when importing the base templates.  They run only when integration
tests are enabled and require network access to OpenAI.
"""

import os
import time
from uuid import uuid4

import pytest
import openai
import weaviate.classes as wvc
from weaviate.classes.config import Property, DataType

pytestmark = pytest.mark.integration

from services.templates import (
    get_template_service_sync,
)
from templates.base import base_templates
from templates.imports import import_templates


# ----------  ENV & CONSTANTS  ------------------------------------------------
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "text-embedding-3-small"


# ----------  HELPERS  --------------------------------------------------------
def openai_embedder(text: str) -> list[float]:
    """Real call to OpenAI embeddings."""
    response = openai.embeddings.create(
        input=text, model=MODEL_NAME, user="template-tests"
    )
    return response.data[0].embedding


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
def collection_name():
    return f"Template_{uuid4().hex[:8]}"


@pytest.fixture
def service(wclient, collection_name):
    # fresh collection
    if wclient.collections.exists(collection_name):
        wclient.collections.delete(collection_name)

    wclient.collections.create(
        name=collection_name,
        vectorizer_config=wvc.config.Configure.Vectorizer.none(),
        properties=[
            Property(name="name", data_type=DataType.TEXT),
            Property(name="title", data_type=DataType.TEXT),
            Property(name="description", data_type=DataType.TEXT),
            Property(name="cypher", data_type=DataType.TEXT),
        ],
    )

    svc = get_template_service_sync(wclient=wclient, embedder=openai_embedder)
    svc.CLASS_NAME = collection_name
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
