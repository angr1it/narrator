import os
import pytest

from config import app_settings  # assumes pydantic-settings loader
from services.templates.service import TemplateService
from templates.imports import import_templates
from templates.base import base_templates  # list of dict templates


@pytest.fixture(scope="session")
def template_service() -> TemplateService:
    """Create a *real* TemplateService bound to a running Weaviate instance.

    The fixture is session‑scoped so we reuse the same connection across tests.
    Skip the test session entirely if the env vars are missing.
    """
    required = [
        app_settings.WEAVIATE_URL,
        getattr(app_settings, "WEAVIATE_API_KEY", None),
        getattr(app_settings, "WEAVIATE_INDEX", None),
        getattr(app_settings, "WEAVIATE_CLASS_NAME", None),
    ]
    if any(v in (None, "") for v in required):
        pytest.skip("Weaviate connection settings are missing – integration tests skipped.")

    return TemplateService(
        weaviate_url=app_settings.WEAVIATE_URL,
        embedder=None,  # rely on Weaviate's vectorizer or nearText fallback
    )


@pytest.fixture(scope="session", autouse=True)
def load_base_templates(template_service: TemplateService):
    """Load all templates from `base_templates` into Weaviate once per session."""
    # Importer already handles upsert semantics and logging.
    import_templates(template_service, base_templates)
    yield  # no teardown – keep data for inspection after tests


def test_templates_present(template_service: TemplateService):
    """Every `id` from base_templates should be retrievable via `get()`."""
    for tpl_dict in base_templates:
        tpl_id = tpl_dict["id"]
        fetched = template_service.get(tpl_id)
        assert fetched.id == tpl_id
        assert fetched.title == tpl_dict["title"]


def test_top_k_returns_relevant(template_service: TemplateService):
    """A semantic query for 'bravery' should rank the trait attribution template in top‑5."""
    results = template_service.top_k("unexpected bravery", k=5)
    ids = [t.id for t in results]
    assert "trait_attribution_v1" in ids


@pytest.mark.parametrize(
    "query,expected_id",
    [
        ("character joins a faction", "membership_change_v1"),
        ("character feels hate", "emotion_state_v1"),
    ],
)
def test_semantic_search_examples(template_service: TemplateService, query: str, expected_id: str):
    """Parametrised smoke‑test for semantic search across two queries."""
    matches = template_service.top_k(query, k=3)
    assert any(t.id == expected_id for t in matches)
