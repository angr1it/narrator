from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Глобовые настройки StoryGraph.

    Поля напрямую «мапятся» на переменные из `.env`.
    Добавлять новые поля → обновлять docker‑compose и README.
    """

    # === Внешние сервисы ===
    OPENAI_API_KEY: str  # OpenAI (SlotFiller)
    NEO4J_URI: str  # neo4j://host:port или bolt://
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    NEO4J_DB: str

    WEAVIATE_URL: str  # Weaviate (TemplateService)
    WEAVIATE_API_KEY: str
    WEAVIATE_CLASS_NAME: str

    MONGO_URI: str | None = None

    LANGFUSE_HOST: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None

    # === Безопасность ===
    AUTH_TOKEN: str  # Простой Bearer‑токен (см. spec «🔐»)

    # === Сервисные параметры ===
    DEBUG: bool = False

    class Config:
        env_file = ".env"  # Читаем из корня проекта


app_settings = AppSettings()  # type: ignore[call-arg]
