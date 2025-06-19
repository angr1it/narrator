import os
import weaviate
from weaviate.classes.init import Auth, AdditionalConfig, Timeout


def connect_to_weaviate(
    *,
    url: str | None = None,
    api_key: str | None = None,
    api_key_env: str = "WEAVIATE_API_KEY",
    openai_api_key_env: str = "OPENAI_API_KEY",
    host: str = "localhost",
    port: int = 8080,
    grpc_port: int = 50051,
    timeout: tuple[int, int, int] | None = None,
    **kwargs,
) -> weaviate.WeaviateClient:
    """
    Универсальное подключение к Weaviate: локально, облако или кастомный кластер.

    Параметры:
    - url: Полный URL кластера Weaviate. Если не указан, подключение будет локальным.
    - api_key: API-ключ для облачного кластера Weaviate. Если не указан, будет использован ключ из переменной окружения.
    - api_key_env: Название переменной окружения с API-ключом Weaviate.
    - openai_api_key_env: Название переменной окружения с API-ключом OpenAI.
    - host, port, grpc_port: Параметры для локального подключения.
    - timeout: Кортеж таймаутов (init, query, insert) в секундах.
    - **kwargs: Дополнительные параметры для клиента Weaviate.

    Возвращает:
    - Экземпляр клиента Weaviate.
    """
    headers = {}
    if openai_key := os.getenv(openai_api_key_env):
        headers["X-OpenAI-Api-Key"] = openai_key

    if not url:
        # Локальное подключение
        return weaviate.connect_to_local(
            host=host,
            port=port,
            grpc_port=grpc_port,
            headers=headers or None,
            **kwargs,
        )

    # Определение метода подключения на основе URL
    if "weaviate.cloud" in url:
        # Подключение к облачному кластеру
        if not api_key:
            api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(
                f"API-ключ не найден в переменной окружения '{api_key_env}'"
            )
        return weaviate.connect_to_weaviate_cloud(
            cluster_url=url,
            auth_credentials=Auth.api_key(api_key),
            headers=headers or None,
            **kwargs,
        )

    # Кастомное подключение
    http_secure = url.startswith("https://")
    grpc_secure = http_secure
    additional_config = None
    if timeout:
        init_t, query_t, insert_t = timeout
        additional_config = AdditionalConfig(
            timeout=Timeout(init=init_t, query=query_t, insert=insert_t)
        )

    return weaviate.connect_to_custom(
        http_host=host,
        http_port=port,
        http_secure=http_secure,
        grpc_host=host,
        grpc_port=grpc_port,
        grpc_secure=grpc_secure,
        headers=headers or None,
        additional_config=additional_config,
        **kwargs,
    )
