"""TemplateService CRUD and search tests.

These tests exercise :class:`TemplateService` against a real Weaviate instance
without requiring OpenAI embeddings.  They create a temporary collection for
each run and validate various behaviours such as upsert, retrieval and
semantic search.
"""

import pytest
from uuid import uuid4
from datetime import datetime

pytestmark = pytest.mark.integration


from services.templates import (
    CypherTemplateBase,
    CypherTemplate,
    TemplateService,
)

from templates.imports import import_templates
from templates.base import base_templates


@pytest.fixture
def test_collection_name():
    """Генерируем уникальное имя коллекции для теста."""
    return f"TestCypherTemplate_{uuid4().hex[:8]}"


@pytest.fixture
def template_service(wclient, test_collection_name):
    if wclient.collections.exists(test_collection_name):
        wclient.collections.delete(test_collection_name)

    svc = TemplateService(
        weaviate_client=wclient,
        embedder=None,
        class_name=test_collection_name,
    )
    yield svc
    wclient.collections.delete(test_collection_name)


# ---------- SAMPLE DATA ------------------------------------------------------
def make_template(slug: str, title: str = "Default Title") -> CypherTemplateBase:
    return CypherTemplateBase(
        name=slug,
        title=title,
        description="Some description",
        slots={},
        cypher="// sample cypher",
        return_map={},
    )


# ---------- TEST CASES -------------------------------------------------------
def test_upsert_insert_and_update(template_service):
    tpl = make_template("slug-upsert")
    saved = template_service.upsert(tpl)
    assert isinstance(saved, CypherTemplate)
    assert saved.id

    # Update with new title
    updated_tpl = make_template("slug-upsert", title="Updated Title")
    saved2 = template_service.upsert(updated_tpl)
    assert saved.id == saved2.id
    assert saved2.title == "Updated Title"


def test_get_and_get_by_name(template_service):
    tpl = make_template("slug-get")
    saved = template_service.upsert(tpl)

    fetched = template_service.get(saved.id)
    assert fetched.name == "slug-get"

    fetched_by_name = template_service.get_by_name("slug-get")
    assert fetched_by_name.id == saved.id


def test_top_k_search(template_service):
    tpl1 = make_template("slug1", title="First Template")
    tpl2 = make_template("slug2", title="Second Template")
    template_service.upsert(tpl1)
    template_service.upsert(tpl2)

    top_results = template_service.top_k("First", k=1)
    assert len(top_results) == 1
    assert top_results[0].name in ["slug1", "slug2"]


def test_import_base_templates(template_service):
    # Импортируем базовые шаблоны
    import_templates(template_service, base_templates)

    # Проверяем, что каждый шаблон успешно импортирован
    for tpl_dict in base_templates:
        tpl_id = tpl_dict["name"]
        fetched = template_service.get_by_name(tpl_id)
        assert fetched.name == tpl_id
        assert fetched.title == tpl_dict["title"]
        assert fetched.cypher == tpl_dict["cypher"]
