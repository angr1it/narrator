"""С Монго все плохо."""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from config import app_settings

# Получение строки подключения из конфигурации
MONGO_URI = app_settings.MONGO_URI
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in app_settings")


def get_mongo_client() -> MongoClient:
    """
    Создаёт и возвращает экземпляр клиента Монго с проверкой соединения.

    :return: Подключённый экземпляр MongoClient.
    :raises RuntimeError: Если подключение не удалось.
    """

    mongo_uri = app_settings.MONGO_URI
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set in app_settings")

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return client
    except ConnectionFailure as e:
        raise RuntimeError("Failed to connect to MongoDB") from e
