from services.templates import TemplateService
from config import app_settings
from config.weaviate import connect_to_weaviate


weaviate_client = connect_to_weaviate(
    url=app_settings.WEAVIATE_URL,
    api_key=app_settings.WEAVIATE_API_KEY,
)

template_service = TemplateService(
    weaviate_client=weaviate_client,
)
