from typing import Callable, List
import openai
from config import app_settings

EmbedderFn = Callable[[str], List[float]]


def openai_embedder(text: str) -> list[float]:
    """
    Функция для получения 1536-мерного эмбеддинга текста через OpenAI API.
    Ключ API передается как параметр.
    """
    openai.api_key = app_settings.OPENAI_API_KEY

    response = openai.embeddings.create(model="text-embedding-3-small", input=text)
    embedding = response.data[0].embedding
    return embedding
