import os
import openai
import pytest

from config import app_settings
from config.weaviate import connect_to_weaviate
from services.templates.service import TemplateService
from templates.imports import import_templates
from templates.base import base_templates


OPENAI_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "text-embedding-3-small"


@pytest.fixture(scope="session")
def weaviate_client():
    """Создаём клиент Weaviate через универсальную функцию подключения."""
    return connect_to_weaviate(
        url=app_settings.WEAVIATE_URL,
        api_key=app_settings.WEAVIATE_API_KEY,
    )


def openai_embedder(text: str) -> list[float]:
    """Real call to OpenAI embeddings."""
    response = openai.embeddings.create(
        input=text, model=MODEL_NAME, user="template-tests"
    )
    return response.data[0].embedding


@pytest.fixture(scope="session")
def template_service(weaviate_client) -> TemplateService:
    """Создаём TemplateService, передавая готовый Weaviate client."""
    required = [
        app_settings.WEAVIATE_URL,
        getattr(app_settings, "WEAVIATE_API_KEY", None),
        getattr(app_settings, "WEAVIATE_INDEX", None),
        getattr(app_settings, "WEAVIATE_CLASS_NAME", None),
    ]
    if any(v in (None, "") for v in required):
        pytest.skip(
            "Weaviate connection settings are missing – integration tests skipped."
        )

    return TemplateService(weaviate_client=weaviate_client, embedder=openai_embedder)


@pytest.fixture(scope="session", autouse=True)
def load_base_templates(template_service: TemplateService):
    """Load all templates from `base_templates` into Weaviate once per session."""
    # Importer already handles upsert semantics and logging.
    import_templates(template_service, base_templates)
    yield  # no teardown – keep data for inspection after tests


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
