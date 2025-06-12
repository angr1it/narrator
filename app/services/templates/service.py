from functools import lru_cache

from services.templates import TemplateService
from config import app_settings
from config.weaviate import connect_to_weaviate
from config.embeddings import openai_embedder


@lru_cache()
def get_weaviate_client():
    """Create and cache a Weaviate client."""
    return connect_to_weaviate(
        url=app_settings.WEAVIATE_URL,
        api_key=app_settings.WEAVIATE_API_KEY,
    )


@lru_cache()
def get_template_service() -> TemplateService:
    """Return a configured TemplateService instance."""
    return TemplateService(
        weaviate_client=get_weaviate_client(),
        embedder=openai_embedder,
    )
