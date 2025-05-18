from services.templates import TemplateService
from config import app_settings


template_service = TemplateService(
    weaviate_url=app_settings.WEAVIATE_URL,
    weaviate_api_key=app_settings.WEAVIATE_API_KEY,
    weaviate_index=app_settings.WEAVIATE_INDEX,
    weaviate_class_name=app_settings.WEAVIATE_CLASS_NAME,
)
