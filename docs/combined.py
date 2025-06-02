# ===== ./main.py =====
from fastapi import FastAPI

from app.api import api_router


app = FastAPI(title="StoryGraph Prototype – spaCy")

app.include_router(api_router, prefix="/v1", tags=["v1"])


@app.get("/v1/sys/health")
def health():
    return {"status": "ok"}


# ===== ./combined.py =====


# ===== ./core/auth/__init__.py =====
from fastapi import Header, HTTPException, status

from config import app_settings


def get_token_header(authorization: str = Header(...)) -> str:
    """Проверяет Bearer‑токен из заголовка Authorization."""
    token = authorization.replace("Bearer ", "")
    if token != app_settings.AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return token


# ===== ./core/slots/prompts/__init__.py =====
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from utils.helpers.cypher import cypher_escape

PROMPT_DIR = Path(__file__).parent / "jinja"
print(f"PROMPT_DIR: {PROMPT_DIR}")

PROMPTS_ENV = Environment(
    loader=FileSystemLoader(PROMPT_DIR),
    autoescape=select_autoescape(),
    undefined=StrictUndefined,
    finalize=cypher_escape, 
)

# ===== ./tempates/base.py =====
# base_templates = [
#     {
#         "id": "trait_attribution_v1",
#         "version": "1.0.0",
#         "title": "Trait attribution",
#         "description": "Character gains, reveals or is attributed a personal trait.",
#         "details": "The protagonist might demonstrate unexpected bravery during a crisis, a supporting character could reveal their intelligence through solving a complex puzzle, or a villain's cruelty might become evident through their actions. This captures moments where a character's nature or qualities become apparent through the narrative.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character", "type": "STRING", "description": "Character name"},
#             {
#                 "name": "trait",
#                 "type": "STRING",
#                 "description": "Trait or quality name",
#             },
#             {"name": "chapter", "type": "INT", "description": "Chapter number"},
#             {
#                 "name": "summary",
#                 "type": "STRING",
#                 "required": False,
#                 "description": "Brief explanation",
#             },
#         ],
#         "cypher": "trait_attribution_v1.j2",
#         "fact_descriptor": {
#             "predicate": "HAS_TRAIT",
#             "subject": "$character",
#             "value": "$trait",
#             "object": "$trait",
#         },
#     },
#     {
#         "id": "membership_change_v1",
#         "version": "1.0.0",
#         "title": "Membership change",
#         "description": "Character joins, leaves or betrays a faction. This includes scenarios where a knight pledges allegiance to a new lord, a spy infiltrates an enemy organization, a rebel abandons their cause after a crisis of conscience, or a long-standing member is expelled from their guild for breaking rules. Any narrative moment that changes a character's affiliation or group membership.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character", "type": "STRING", "description": "Character name"},
#             {"name": "faction", "type": "STRING", "description": "Faction name"},
#             {"name": "chapter", "type": "INT", "description": "Chapter number"},
#             {"name": "summary", "type": "STRING", "required": False},
#         ],
#         "cypher": "membership_change_v1.j2",
#         "fact_descriptor": {
#             "predicate": "MEMBER_OF",
#             "subject": "$character",
#             "value": "$faction",
#             "object": "$faction",
#         },
#     },
#     {
#         "id": "character_relation_v1",
#         "version": "1.0.0",
#         "title": "Character relation",
#         "description": "Creates or updates a social relation between two characters (ally, rival, sibling, parent, etc.). This captures situations where characters discover they're long-lost siblings, former friends become bitter enemies after a betrayal, strangers form a strategic alliance against a common threat, or a mentor takes on a new apprentice. Any significant development or change in how two characters relate to each other.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character_a", "type": "STRING", "description": "First character"},
#             {
#                 "name": "character_b",
#                 "type": "STRING",
#                 "description": "Second character",
#             },
#             {
#                 "name": "relation_type",
#                 "type": "STRING",
#                 "description": "Relation type: ALLY, RIVAL, SIBLING, PARENT",
#             },
#             {"name": "chapter", "type": "INT"},
#             {"name": "summary", "type": "STRING", "required": False},
#         ],
#         "cypher": "character_relation_v1.j2",
#         "fact_descriptor": {
#             "predicate": "RELATION_WITH",
#             "subject": "$character_a",
#             "value": "$relation_type",
#             "object": "$character_b",
#         },
#     },
#     {
#         "id": "ownership_v1",
#         "version": "1.0.0",
#         "title": "Item ownership",
#         "description": "Character acquires or possesses an item. This includes a hero finding an ancient magical sword, a thief stealing a valuable artifact, a character receiving a meaningful gift or heirloom, or someone purchasing an important tool for their quest. Any narrative moment where a character gains possession of something significant to the story.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character", "type": "STRING"},
#             {"name": "item", "type": "STRING"},
#             {"name": "chapter", "type": "INT"},
#             {"name": "summary", "type": "STRING", "required": False},
#         ],
#         "cypher": "ownership_v1.j2",
#         "fact_descriptor": {
#             "predicate": "OWNS_ITEM",
#             "subject": "$character",
#             "value": "$item",
#             "object": "$item",
#         },
#     },
#     {
#         "id": "relocation_v1",
#         "version": "1.0.0",
#         "title": "Relocation / arrives at place",
#         "description": "Character changes location, arrives or leaves a place. This captures a traveler reaching a mysterious new city, a refugee fleeing their homeland, an explorer discovering uncharted territory, or a prisoner escaping their cell. Any significant movement of characters between meaningful locations in the narrative landscape.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character", "type": "STRING"},
#             {"name": "place", "type": "STRING"},
#             {"name": "chapter", "type": "INT"},
#             {"name": "summary", "type": "STRING", "required": False},
#         ],
#         "cypher": "relocation_v1.j2",
#         "fact_descriptor": {
#             "predicate": "AT_LOCATION",
#             "subject": "$character",
#             "value": "$place",
#             "object": "$place",
#         },
#     },
#     {
#         "id": "emotion_state_v1",
#         "version": "1.0.0",
#         "title": "Emotional state toward target",
#         "description": "Character feels an emotion toward another character or in general. This applies when a protagonist develops feelings of love for another character, a villain's hatred intensifies after defeat, a character experiences profound grief following a loss, or someone struggles with jealousy over another's success. Captures the emotional landscape and psychological developments driving character motivations.",
#         "category": "EventInsert",
#         "slots": [
#             {
#                 "name": "character",
#                 "type": "STRING",
#                 "description": "Name of the character",
#             },
#             {
#                 "name": "emotion",
#                 "type": "STRING",
#                 "description": "Emotion name, e.g., HATE, LOVE",
#             },
#             {
#                 "name": "target",
#                 "type": "STRING",
#                 "description": "Target of the emotion",
#                 "required": False,
#             },
#             {"name": "chapter", "type": "INT", "description": "Chapter number"},
#             {
#                 "name": "summary",
#                 "type": "STRING",
#                 "description": "Narrative summary",
#                 "required": False,
#             },
#         ],
#         "cypher": "emotion_state_v1.j2",
#         "fact_descriptor": {
#             "predicate": "FEELS",
#             "subject": "$character",
#             "value": "$emotion",
#             "object": "$target",
#         },
#     },
#     {
#         "id": "vow_promise_v1",
#         "version": "1.0.0",
#         "title": "Vow or promise",
#         "description": "Character makes a vow, promise or obligation toward a goal or target. This includes a knight swearing to avenge their fallen comrade, a character pledging to protect someone vulnerable, a villain making a threat of retribution, or someone committing to an important personal goal. Any declaration of intent or commitment that drives future narrative actions.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character", "type": "STRING"},
#             {"name": "goal", "type": "STRING", "description": "Promise essence / goal"},
#             {"name": "chapter", "type": "INT"},
#             {"name": "summary", "type": "STRING", "required": False},
#         ],
#         "cypher": "vow_promise_v1.j2",
#         "fact_descriptor": {
#             "predicate": "VOWS",
#             "subject": "$character",
#             "value": "$goal",
#             "object": "$goal",
#         },
#     },
#     {
#         "id": "death_event_v1",
#         "version": "1.0.0",
#         "title": "Death of character",
#         "description": "Marks a character as deceased. This applies to heroic sacrifices in battle, victims of murder or assassination, natural deaths of significance to the plot, or presumed deaths later revealed to be false. Captures pivotal moments where a character's life ends or is believed to end, changing the trajectory of the narrative.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character", "type": "STRING"},
#             {"name": "chapter", "type": "INT"},
#             {"name": "summary", "type": "STRING", "required": False},
#         ],
#         "cypher": "death_event_v1.j2",
#         "fact_descriptor": {
#             "predicate": "IS_ALIVE",
#             "subject": "$character",
#             "value": "false",
#         },
#     },
#     {
#         "id": "belief_ideology_v1",
#         "version": "1.0.0",
#         "title": "Belief or ideology",
#         "description": "Character professes belief in deity, ideology or philosophy. This includes a character's conversion to a new religion after a profound experience, a politician embracing a radical ideology, someone finding comfort in spiritual practices during hardship, or a character questioning and abandoning their long-held beliefs. Reflects the philosophical and spiritual dimensions that shape character motivations and worldviews.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character", "type": "STRING"},
#             {
#                 "name": "ideology",
#                 "type": "STRING",
#                 "description": "Name of ideology, deity or belief",
#             },
#             {"name": "chapter", "type": "INT"},
#             {"name": "summary", "type": "STRING", "required": False},
#         ],
#         "cypher": "belief_ideology_v1.j2",
#         "fact_descriptor": {
#             "predicate": "BELIEVES_IN",
#             "subject": "$character",
#             "value": "$ideology",
#             "object": "$ideology",
#         },
#     },
#     {
#         "id": "title_acquisition_v1",
#         "version": "1.0.0",
#         "title": "Title acquisition",
#         "description": "Character receives or is granted a new title or role. This captures a soldier's promotion to general, a commoner ascending to nobility, an apprentice becoming a master of their craft, or someone being appointed to a position of authority. Any formal recognition or change in status that affects how others perceive and interact with the character within the narrative.",
#         "category": "EventInsert",
#         "slots": [
#             {"name": "character", "type": "STRING"},
#             {
#                 "name": "title_name",
#                 "type": "STRING",
#                 "description": "Title/role name",
#             },
#             {"name": "chapter", "type": "INT"},
#             {"name": "summary", "type": "STRING", "required": False},
#         ],
#         "cypher": "title_acquisition_v1.j2",
#         "fact_descriptor": {
#             "predicate": "HAS_TITLE",
#             "subject": "$character",
#             "value": "$title_name",
#             "object": "$title_name",
#         },
#     },
# ]


# ===== ./config/mongo_db.py =====
"""С Монго все плохо."""
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Получение строки из энв.
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in environment")


def get_mongo_client() -> MongoClient:
    """
    Создаёт и возвращает экземпляр клиента Монго с проверкой соединения.

    :return: Подключённый экземпляр MongoClient.
    :raises RuntimeError: Если подключение не удалось.
    """

    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set in environment")

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return client
    except ConnectionFailure as e:
        raise RuntimeError("Failed to connect to MongoDB") from e


# ===== ./config/neo4j.py =====


# ===== ./config/__init__.py =====
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
    WEAVIATE_INDEX: str
    WEAVIATE_CLASS_NAME: str

    LANGFUSE_HOST: str | None = None
    LANGFUSE_PUBLIC: str | None = None
    LANGFUSE_SECRET: str | None = None

    # === Безопасность ===
    AUTH_TOKEN: str  # Простой Bearer‑токен (см. spec «🔐»)

    # === Сервисные параметры ===
    DEBUG: bool = False

    class Config:
        env_file = ".env"  # Читаем из корня проекта


app_settings = AppSettings()


# ===== ./config/embeddings.py =====
import openai
from config import app_settings


def openai_embedder(text: str) -> list[float]:
    """
    Функция для получения 1536-мерного эмбеддинга текста через OpenAI API.
    Ключ API передается как параметр.
    """
    openai.api_key = app_settings.OPENAI_API_KEY

    response = openai.embeddings.create(model="text-embedding-3-small", input=text)
    embedding = response.data[0].embedding
    return embedding


# ===== ./config/weaviate.py =====
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
        additional_config = AdditionalConfig(timeout=Timeout(*timeout))

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

# ===== ./tests/conftest.py =====
import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Единый цикл на всю pytest‑сессию — избавляет от конфликтов asyncpg."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ===== ./tests/services/test_template_service_integration.py =====
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


# ===== ./tests/services/integration/test_slot_service.py =====
import pytest
from uuid import uuid4

from services.slot_filler import SlotFiller
from schemas.cypher import CypherTemplate, SlotDefinition
from config import app_settings

# --- FIXTURES ---------------------------------------------------------------

FIXED_UUID = uuid4()

@pytest.fixture(scope="module")
def openai_key() -> str:
    key = app_settings.OPENAI_API_KEY
    assert key, "Set OPENAI_API_KEY in environment to run integration tests"
    return key


@pytest.fixture
def base_template() -> CypherTemplate:
    return CypherTemplate(
        id=FIXED_UUID,
        name="membership_change",
        title="Membership change",
        description="Когда персонаж покидает одну фракцию и вступает в другую",
        slots={
            "character": SlotDefinition(
                name="character", type="STRING", description="Имя героя", required=True
            ),
            "faction": SlotDefinition(
                name="faction",
                type="STRING",
                description="Название фракции",
                required=True,
            ),
            "summary": SlotDefinition(
                name="summary",
                type="STRING",
                description="Краткое описание",
                required=False,
            ),
        },
        cypher="mock.cypher",
    )


@pytest.fixture
def filler(openai_key) -> SlotFiller:
    return SlotFiller(api_key=openai_key, temperature=0.0)


# --- TEST CASES -------------------------------------------------------------


def test_extract_multiple_results(
    filler: SlotFiller, base_template: CypherTemplate
):
    text = "Арен покинул Дом Зари и примкнул к Северному фронту."
    results = filler.fill_slots(base_template, text)

    assert isinstance(results, list)
    assert len(results) >= 2

    for r in results:
        assert r["template_id"] == FIXED_UUID
        assert "character" in r["slots"]
        assert "faction" in r["slots"]
        assert "details" in r
        assert isinstance(r["details"], str)


def test_extract_missing_then_generate(filler: SlotFiller):
    template = CypherTemplate(
        id=FIXED_UUID,
        name="emotion_event",
        title="Emotion expression",
        description="Персонаж выражает эмоцию к другому персонажу",
        slots={
            "subject": SlotDefinition(
                name="subject",
                type="STRING",
                description="Кто испытывает эмоцию",
                required=True,
            ),
            "target": SlotDefinition(
                name="target",
                type="STRING",
                description="На кого направлена эмоция",
                required=True,
            ),
            "emotion": SlotDefinition(
                name="emotion", type="STRING", description="Тип эмоции", required=True
            ),
            "summary": SlotDefinition(
                name="summary",
                type="STRING",
                description="Описание сцены",
                required=False,
            ),
        },
        cypher="mock.cypher",
    )
    text = "Мира посмотрела на Эрика с презрением."
    results = filler.fill_slots(template, text)

    assert results
    for r in results:
        slots = r["slots"]
        assert slots["subject"] == "Мира"
        assert slots["target"] == "Эрик"
        assert "emotion" in slots
        assert "details" in r
        if "summary" in slots:
            assert isinstance(slots["summary"], str)


def test_extract_single_object(filler: SlotFiller):
    template = CypherTemplate(
        id=FIXED_UUID,
        name="trait_reveal",
        title="Trait reveal",
        description="Когда персонаж раскрывает черту другого",
        slots={
            "actor": SlotDefinition(
                name="actor", type="STRING", description="Кто раскрыл", required=True
            ),
            "trait": SlotDefinition(
                name="trait", type="STRING", description="Какая черта", required=True
            ),
        },
        cypher="mock.cypher",
    )
    text = "Мира раскрыла, что Арен с рождения был одноруким."
    results = filler.fill_slots(template, text)

    assert len(results) == 1
    r = results[0]
    assert r["slots"]["actor"] == "Мира"
    assert "trait" in r["slots"]
    assert "details" in r


# ===== ./tests/services/integration/test_template_service.py =====
import os
import pytest
from uuid import uuid4
from datetime import datetime
from typing import List

import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Property, DataType

from services.templates import TemplateService, CypherTemplateBase, CypherTemplate
from config.weaviate import connect_to_weaviate
from templates.imports import import_templates
from templates.base import base_templates


# ---------- GLOBAL TEST CONSTANTS -------------------------------------------
LOCAL_WEAVIATE_URL = "http://localhost:8080"


# ---------- PYTEST FIXTURES -------------------------------------------------
@pytest.fixture(scope="session")
def wclient():
    """Подключение к локальному Weaviate."""
    client = connect_to_weaviate(url=None)  # → localhost
    assert client.is_ready(), "Weaviate локальный не готов"
    yield client
    client.close()


@pytest.fixture
def test_collection_name():
    """Генерируем уникальное имя коллекции для теста."""
    return f"TestCypherTemplate_{uuid4().hex[:8]}"


@pytest.fixture
def template_service(wclient, test_collection_name):
    """Создаём TemplateService c тестовой коллекцией."""
    # --- создаём схему коллекции ---
    if wclient.collections.exists(test_collection_name):
        wclient.collections.delete(test_collection_name)

    wclient.collections.create(
        name=test_collection_name,
        vectorizer_config=wvc.config.Configure.Vectorizer.none(),
        inverted_index_config=wvc.config.Configure.inverted_index(),
        properties=[
            Property(name="name", data_type=DataType.TEXT),
            Property(name="title", data_type=DataType.TEXT),
            Property(name="description", data_type=DataType.TEXT),
            Property(name="cypher", data_type=DataType.TEXT),
        ],
    )

    # --- создаём сервис ---
    service = TemplateService(
        weaviate_client=wclient,
        embedder=lambda text: [0.1, 0.2, 0.3],  # фиктивный embedder
    )
    service.CLASS_NAME = test_collection_name  # переназначаем имя коллекции

    yield service

    # --- подчищаем коллекцию после теста ---
    wclient.collections.delete(test_collection_name)


# ---------- SAMPLE DATA ------------------------------------------------------
def make_template(slug: str, title: str = "Default Title") -> CypherTemplateBase:
    return CypherTemplateBase(
        name=slug,
        title=title,
        description="Some description",
        slots={},
        cypher="// sample cypher",
        created_at=datetime.utcnow(),
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


# ===== ./tests/services/integration/test_slot_integration.py =====
import pytest

from schemas.cypher import CypherTemplate, FactDescriptor, SlotDefinition
from services.slot_filler import SlotFiller
from templates.base import base_templates
from config import app_settings


@pytest.fixture(scope="module")
def openai_key() -> str:
    key = app_settings.OPENAI_API_KEY
    assert key, "Установите переменную окружения OPENAI_API_KEY для теста"
    return key


@pytest.fixture
def trait_template() -> CypherTemplate:
    template_dict = base_templates[0]

    slots = [SlotDefinition(**s) for s in template_dict["slots"]]
    fact_desc = FactDescriptor(**template_dict["fact_descriptor"])

    return CypherTemplate(
        id=template_dict["id"],
        version=template_dict["version"],
        title=template_dict["title"],
        description=template_dict["description"],
        category=template_dict["category"],
        slots=slots,
        fact_descriptor=fact_desc,
        cypher=template_dict["cypher"],
    )


@pytest.fixture
def filler(openai_key: str) -> SlotFiller:
    # Температуру ставим 0 для большей детерминированности на тестах
    return SlotFiller(api_key=openai_key, temperature=0.0)


def test_trait_attribution_end_to_end(
    filler: SlotFiller, trait_template: CypherTemplate
):
    """
    Проверяем, что SlotFiller извлекает все обязательные слоты:
    character, trait, chapter + генерирует summary (необязательный).
    """
    text = (
        "В 10-й главе Арен проявил невероятную храбрость, "
        "бросившись спасать товарища из горящего здания."
    )

    results = filler.fill_slots(trait_template, text)

    # Ожидаем хотя бы один результат
    assert results, "LLM не вернул ни одного заполнения"

    item = results[0]
    slots = item["slots"]

    # Обязательные поля
    assert slots["character"].lower().startswith("арен")
    assert "храбр" in slots["trait"].lower()  # модификатор на русский корень
    assert int(slots["chapter"]) == 10

    # "summary" генерируется (может отсутствовать, если модель не сгенерирует)
    if "summary" in slots:
        assert isinstance(slots["summary"], str) and len(slots["summary"]) > 0

    # details присутствуют
    assert "details" in item and isinstance(item["details"], str)


# ===== ./tests/services/integration/test_template_service_openai.py =====
# tests/test_template_service_openai.py
import os
import time
from uuid import uuid4
from datetime import datetime

import pytest
import openai
import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Property, DataType
from weaviate.classes.query import Filter

from services.templates import TemplateService, CypherTemplateBase
from config.weaviate import connect_to_weaviate
from templates.base import base_templates
from templates.imports import import_templates


# ----------  ENV & CONSTANTS  ------------------------------------------------
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "text-embedding-3-small"
LOCAL_WEAVIATE = "http://localhost:8080"


# ----------  HELPERS  --------------------------------------------------------
def openai_embedder(text: str) -> list[float]:
    """Real call to OpenAI embeddings."""
    response = openai.embeddings.create(
        input=text, model=MODEL_NAME, user="template-tests"
    )
    return response.data[0].embedding


def narrative_samples():
    """(query, expected slug) pairs close to production usage."""
    return [
        # (
        #     "During the siege Arya displayed unexpected bravery saving her comrades.",
        #     "trait_attribution_v1",
        # ),
        (
            "Sir Lancel renounced his vows and pledged allegiance to the rebel lord.",
            "membership_change_v1",
        ),
        (
            "Jon finally accepted Sansa as his sister and ally against their enemies.",
            "character_relation_v1",
        ),
    ]


# ----------  PYTEST FIXTURES  ------------------------------------------------
@pytest.fixture(scope="session")
def wclient():
    if not OPENAI_KEY:
        pytest.skip("OPENAI_API_KEY not set")
    openai.api_key = OPENAI_KEY

    client = connect_to_weaviate(url=None)  # localhost
    if not client.is_ready():
        pytest.skip("Local Weaviate is not running")
    yield client
    client.close()


@pytest.fixture
def collection_name():
    return f"Template_{uuid4().hex[:8]}"


@pytest.fixture
def service(wclient, collection_name):
    # fresh collection
    if wclient.collections.exists(collection_name):
        wclient.collections.delete(collection_name)

    wclient.collections.create(
        name=collection_name,
        vectorizer_config=wvc.config.Configure.Vectorizer.none(),
        properties=[
            Property(name="name", data_type=DataType.TEXT),
            Property(name="title", data_type=DataType.TEXT),
            Property(name="description", data_type=DataType.TEXT),
            Property(name="cypher", data_type=DataType.TEXT),
        ],
    )

    svc = TemplateService(wclient, embedder=openai_embedder)
    svc.CLASS_NAME = collection_name
    yield svc
    wclient.collections.delete(collection_name)


# ----------  TESTS  ----------------------------------------------------------
def test_bulk_import_and_semantic_search(service):
    # -------- 1) bulk import
    import_templates(service, base_templates)

    # небольшая пауза, чтобы HNSW успел проиндексировать
    time.sleep(1.0)

    # -------- 2) direct retrieval sanity
    for tpl in base_templates:
        obj = service.get_by_name(tpl["name"])
        assert obj.title == tpl["title"]

    # -------- 3) semantic search with real embeddings
    for query, expected_slug in narrative_samples():
        hits = service.top_k(query, k=1)
        assert hits, f"No result for query: {query}"
        assert hits[0].name == expected_slug


# ===== ./utils/logger/__init__.py =====
import logging


def get_logger(name=__name__):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(name)s - %(levelname)s - %(funcName)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    if not logger.hasHandlers():
        logger.addHandler(console_handler)

    return logger


# ===== ./utils/helpers/cypher.py =====
def cypher_escape(value):
    """Экранирует строку для Cypher:  ' → \',  \\ → \\\\"""
    if isinstance(value, str):
        return value.replace("\\", "\\\\").replace("'", "\\'")
    return value


# ===== ./schemas/fact.py =====
from pydantic import BaseModel
from typing import Optional, List


class Fact(BaseModel):
    # ── required ─────────────────────────────────────────────────────────
    id: str                                # generated in Cypher (uuid)
    predicate: str                         # e.g. HAS_TRAIT, MEMBER_OF …
    subject: str                           # node-id or name of the subject
    # ── optional but COMMON ──────────────────────────────────────────────
    object: Optional[str] = None           # node-id of the object (if relation)
    value:      Optional[str] = None       # literal value (if attribute)
    # ── temporal versioning (all optional) ───────────────────────────────
    from_chapter: Optional[int] = None
    to_chapter:   Optional[int] = None
    iso_date:    Optional[str] = None
    # ── narrative metadata ───────────────────────────────────────────────
    summary: Optional[str] = None
    tags:    Optional[List[str]] = None
    # ── vector space  ────────────────────────────────────────────────────
    vector:  Optional[List[float]] = None


# ===== ./schemas/__init__.py =====
from fastapi_camelcase import CamelModel


class ExtractSaveIn(CamelModel):
    chapter: int
    tags: list[str] = []
    text: str


class ExtractSaveOut(CamelModel):
    status: str
    cypher_batch: list[str]
    trace_id: str


class AugmentCtxIn(ExtractSaveIn): ...


class AugmentCtxOut(CamelModel):
    context: list[str, any]
    trace_id: str


# ===== ./schemas/extract.py =====

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ExtractRequest(BaseModel):
    """Запрос на извлечение и сохранение фактов."""

    text: str = Field(..., description="Фрагмент 2–8 предложений")
    chapter: int = Field(..., description="Номер главы (>= 1)")
    tags: Optional[List[str]] = Field(None, description="Ключевые слова")


class ExtractResponse(BaseModel):
    """Ответ API: лог успешных вставок."""

    facts: List[Dict[str, Any]]
    inserted_ids: List[str]



# ===== ./schemas/cypher.py =====
from typing import List, Optional, Literal, Union
from datetime import datetime
import uuid

from pydantic import BaseModel, Field

from templates import TEMPLATE_DIR, env, TemplateNotFound


class SlotDefinition(BaseModel):
    name: str
    type: Literal["STRING", "INT", "FLOAT", "BOOL"]
    description: Optional[str] = None
    required: bool = True
    default: Optional[Union[str, int, float, bool]] = None


class FactDescriptor(BaseModel):
    predicate: str  # e.g. "MEMBER_OF"
    subject: str  # e.g. "$character"
    value: str  # e.g. "$faction"
    object: Optional[str] = None  # e.g. "$faction"


class CypherTemplateBase(BaseModel):
    name: str = Field(..., description="Уникальный slug шаблона")
    version: str = "1.0.0"
    title: str
    description: str
    details: Optional[str] = None
    category: Optional[str] = None
    slots: dict[str, SlotDefinition]
    fact_descriptor: Optional[FactDescriptor] = None
    cypher: str
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    vector: Optional[List[float]] = None

    def render(self, slots: dict) -> str:
        """Рендерит шаблон Cypher на основе переданных значений слотов."""
        required = [slot.name for slot in self.slots.values() if slot.required]
        missing = [name for name in required if name not in slots.keys()]

        if missing:
            raise ValueError(f"Missing required slots: {missing}")

        context = dict(slots)
        if self.fact_descriptor:
            fd = self.fact_descriptor

            def pick(expr: str | None) -> str | None:
                """resolve “$slotName” → actual value or None"""
                if expr and expr.startswith("$"):
                    return slots.get(expr[1:])
                return expr

            context["fact"] = {
                "predicate": fd.predicate,
                "subject": pick(fd.subject),
                "object": pick(fd.object),
                "value": pick(fd.value),
            }
        try:
            template = env.get_template(self.cypher)
        except TemplateNotFound:
            raise ValueError(
                f"Template file '{self.cypher}' not found in {TEMPLATE_DIR}"
            )

        return template.render(**context)


class CypherTemplate(CypherTemplateBase):
    id: uuid.UUID


# ===== ./api/__init__.py =====
from fastapi import APIRouter

from app.api.augment import route as augment_router
from app.api.extract import route as extract_router

api_router = APIRouter()

api_router.include_router(augment_router, tags=["augment"])
api_router.include_router(extract_router, tags=["extract"])


# ===== ./api/augment/__init__.py =====
from fastapi import APIRouter, Depends

from core.auth import token_auth
from schemas import AugmentCtxIn, AugmentCtxOut


route = APIRouter()

@route.post("/augment-context", response_model=AugmentCtxOut)
def augment_ctx(req: AugmentCtxIn, token=Depends(token_auth)):
    return augment_pipeline.run(req.text, {"chapter": req.chapter})


# ===== ./api/extract/__init__.py =====
from fastapi import APIRouter, Depends

from core.auth import token_auth
from schemas import ExtractSaveIn, ExtractSaveOut


route = APIRouter()


@route.post("/extract-save", response_model=ExtractSaveOut)
def extract_save(req: ExtractSaveIn, token=Depends(token_auth)):
    return extract_pipeline.run(req.text, {"chapter": req.chapter})


# ===== ./templates/__init__.py =====
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from utils.helpers.cypher import cypher_escape

TEMPLATE_DIR = "templates/cypher"


env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=False,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    finalize=cypher_escape, 
)


# ===== ./templates/imports.py =====
from typing import List, Union, Dict

from schemas.cypher import CypherTemplateBase
from services.templates import TemplateService
from utils.logger import get_logger


logger = get_logger(__name__)


def import_templates(
    service: TemplateService, templates: List[Union[CypherTemplateBase, Dict]]
) -> None:
    """Bulk import a list of CypherTemplates into Weaviate."""
    for entry in templates:
        if isinstance(entry, dict):
            tpl = CypherTemplateBase(**entry)
        elif isinstance(entry, CypherTemplateBase):
            tpl = entry
        else:
            raise TypeError(f"Invalid template type: {type(entry)}")

        try:
            service.upsert(tpl)
            logger.info(f"✓ Imported template: {tpl.name}")
        except Exception as e:
            logger.warning(f"✗ Failed to import {tpl.name}: {e}")


# ===== ./templates/base.py =====
base_templates = [
    {
        "name": "trait_attribution_v1",
        "version": "1.0.0",
        "title": "Trait attribution",
        "description": "Character gains, reveals or is attributed a personal trait.",
        "details": "The protagonist might demonstrate unexpected bravery during a crisis, a supporting character could reveal their intelligence through solving a complex puzzle, or a villain's cruelty might become evident through their actions. This captures moments where a character's nature or qualities become apparent through the narrative.",
        "category": "EventInsert",
        "slots": {
            "character": {
                "name": "character",
                "type": "STRING",
                "description": "Character name",
            },
            "trait": {
                "name": "trait",
                "type": "STRING",
                "description": "Trait or quality name",
            },
            "chapter": {
                "name": "chapter",
                "type": "INT",
                "description": "Chapter number",
            },
            "summary": {
                "name": "summary",
                "type": "STRING",
                "required": False,
                "description": "Brief explanation",
            },
        },
        "cypher": "trait_attribution_v1.j2",
        "fact_descriptor": {
            "predicate": "HAS_TRAIT",
            "subject": "$character",
            "value": "$trait",
            "object": "$trait",
        },
    },
    {
        "name": "membership_change_v1",
        "version": "1.0.0",
        "title": "Membership change",
        "description": "Character joins, leaves or betrays a faction. This includes scenarios where a knight pledges allegiance to a new lord, a spy infiltrates an enemy organization, a rebel abandons their cause after a crisis of conscience, or a long-standing member is expelled from their guild for breaking rules. Any narrative moment that changes a character's affiliation or group membership.",
        "category": "EventInsert",
        "slots": {
            "character": {
                "name": "character",
                "type": "STRING",
                "description": "Character name",
            },
            "faction": {
                "name": "faction",
                "type": "STRING",
                "description": "Faction name",
            },
            "chapter": {
                "name": "chapter",
                "type": "INT",
                "description": "Chapter number",
            },
            "summary": {"name": "summary", "type": "STRING", "required": False},
        },
        "cypher": "membership_change_v1.j2",
        "fact_descriptor": {
            "predicate": "MEMBER_OF",
            "subject": "$character",
            "value": "$faction",
            "object": "$faction",
        },
    },
    {
        "name": "character_relation_v1",
        "version": "1.0.0",
        "title": "Character relation",
        "description": "Creates or updates a social relation between two characters (ally, rival, sibling, parent, etc.). This captures situations where characters discover they're long-lost siblings, former friends become bitter enemies after a betrayal, strangers form a strategic alliance against a common threat, or a mentor takes on a new apprentice. Any significant development or change in how two characters relate to each other.",
        "category": "EventInsert",
        "slots": {
            "character_a": {
                "name": "character_a",
                "type": "STRING",
                "description": "First character",
            },
            "character_b": {
                "name": "character_b",
                "type": "STRING",
                "description": "Second character",
            },
            "relation_type": {
                "name": "relation_type",
                "type": "STRING",
                "description": "Relation type: ALLY, RIVAL, SIBLING, PARENT",
            },
            "chapter": {"name": "chapter", "type": "INT"},
            "summary": {"name": "summary", "type": "STRING", "required": False},
        },
        "cypher": "character_relation_v1.j2",
        "fact_descriptor": {
            "predicate": "RELATION_WITH",
            "subject": "$character_a",
            "value": "$relation_type",
            "object": "$character_b",
        },
    },
    {
        "name": "ownership_v1",
        "version": "1.0.0",
        "title": "Item ownership",
        "description": "Character acquires or possesses an item. This includes a hero finding an ancient magical sword, a thief stealing a valuable artifact, a character receiving a meaningful gift or heirloom, or someone purchasing an important tool for their quest. Any narrative moment where a character gains possession of something significant to the story.",
        "category": "EventInsert",
        "slots": {
            "character": {"name": "character", "type": "STRING"},
            "item": {"name": "item", "type": "STRING"},
            "chapter": {"name": "chapter", "type": "INT"},
            "summary": {"name": "summary", "type": "STRING", "required": False},
        },
        "cypher": "ownership_v1.j2",
        "fact_descriptor": {
            "predicate": "OWNS_ITEM",
            "subject": "$character",
            "value": "$item",
            "object": "$item",
        },
    },
    {
        "name": "relocation_v1",
        "version": "1.0.0",
        "title": "Relocation / arrives at place",
        "description": "Character changes location, arrives or leaves a place. This captures a traveler reaching a mysterious new city, a refugee fleeing their homeland, an explorer discovering uncharted territory, or a prisoner escaping their cell. Any significant movement of characters between meaningful locations in the narrative landscape.",
        "category": "EventInsert",
        "slots": {
            "character": {"name": "character", "type": "STRING"},
            "place": {"name": "place", "type": "STRING"},
            "chapter": {"name": "chapter", "type": "INT"},
            "summary": {"name": "summary", "type": "STRING", "required": False},
        },
        "cypher": "relocation_v1.j2",
        "fact_descriptor": {
            "predicate": "AT_LOCATION",
            "subject": "$character",
            "value": "$place",
            "object": "$place",
        },
    },
    {
        "name": "emotion_state_v1",
        "version": "1.0.0",
        "title": "Emotional state toward target",
        "description": "Character feels an emotion toward another character or in general. This applies when a protagonist develops feelings of love for another character, a villain's hatred intensifies after defeat, a character experiences profound grief following a loss, or someone struggles with jealousy over another's success. Captures the emotional landscape and psychological developments driving character motivations.",
        "category": "EventInsert",
        "slots": {
            "character": {
                "name": "character",
                "type": "STRING",
                "description": "Name of the character",
            },
            "emotion": {
                "name": "emotion",
                "type": "STRING",
                "description": "Emotion name, e.g., HATE, LOVE",
            },
            "target": {
                "name": "target",
                "type": "STRING",
                "description": "Target of the emotion",
                "required": False,
            },
            "chapter": {
                "name": "chapter",
                "type": "INT",
                "description": "Chapter number",
            },
            "summary": {
                "name": "summary",
                "type": "STRING",
                "description": "Narrative summary",
                "required": False,
            },
        },
        "cypher": "emotion_state_v1.j2",
        "fact_descriptor": {
            "predicate": "FEELS",
            "subject": "$character",
            "value": "$emotion",
            "object": "$target",
        },
    },
    {
        "name": "vow_promise_v1",
        "version": "1.0.0",
        "title": "Vow or promise",
        "description": "Character makes a vow, promise or obligation toward a goal or target. This includes a knight swearing to avenge their fallen comrade, a character pledging to protect someone vulnerable, a villain making a threat of retribution, or someone committing to an important personal goal. Any declaration of intent or commitment that drives future narrative actions.",
        "category": "EventInsert",
        "slots": {
            "character": {"name": "character", "type": "STRING"},
            "goal": {
                "name": "goal",
                "type": "STRING",
                "description": "Promise essence / goal",
            },
            "chapter": {"name": "chapter", "type": "INT"},
            "summary": {"name": "summary", "type": "STRING", "required": False},
        },
        "cypher": "vow_promise_v1.j2",
        "fact_descriptor": {
            "predicate": "VOWS",
            "subject": "$character",
            "value": "$goal",
            "object": "$goal",
        },
    },
    {
        "name": "death_event_v1",
        "version": "1.0.0",
        "title": "Death of character",
        "description": "Marks a character as deceased. This applies to heroic sacrifices in battle, victims of murder or assassination, natural deaths of significance to the plot, or presumed deaths later revealed to be false. Captures pivotal moments where a character's life ends or is believed to end, changing the trajectory of the narrative.",
        "category": "EventInsert",
        "slots": {
            "character": {"name": "character", "type": "STRING"},
            "chapter": {"name": "chapter", "type": "INT"},
            "summary": {"name": "summary", "type": "STRING", "required": False},
        },
        "cypher": "death_event_v1.j2",
        "fact_descriptor": {
            "predicate": "IS_ALIVE",
            "subject": "$character",
            "value": "false",
        },
    },
    {
        "name": "belief_ideology_v1",
        "version": "1.0.0",
        "title": "Belief or ideology",
        "description": "Character professes belief in deity, ideology or philosophy. This includes a character's conversion to a new religion after a profound experience, a politician embracing a radical ideology, someone finding comfort in spiritual practices during hardship, or a character questioning and abandoning their long-held beliefs. Reflects the philosophical and spiritual dimensions that shape character motivations and worldviews.",
        "category": "EventInsert",
        "slots": {
            "character": {"name": "character", "type": "STRING"},
            "ideology": {
                "name": "ideology",
                "type": "STRING",
                "description": "Name of ideology, deity or belief",
            },
            "chapter": {"name": "chapter", "type": "INT"},
            "summary": {"name": "summary", "type": "STRING", "required": False},
        },
        "cypher": "belief_ideology_v1.j2",
        "fact_descriptor": {
            "predicate": "BELIEVES_IN",
            "subject": "$character",
            "value": "$ideology",
            "object": "$ideology",
        },
    },
    {
        "name": "title_acquisition_v1",
        "version": "1.0.0",
        "title": "Title acquisition",
        "description": "Character receives or is granted a new title or role. This captures a soldier's promotion to general, a commoner ascending to nobility, an apprentice becoming a master of their craft, or someone being appointed to a position of authority. Any formal recognition or change in status that affects how others perceive and interact with the character within the narrative.",
        "category": "EventInsert",
        "slots": {
            "character": {"name": "character", "type": "STRING"},
            "title_name": {
                "name": "title_name",
                "type": "STRING",
                "description": "Title/role name",
            },
            "chapter": {"name": "chapter", "type": "INT"},
            "summary": {"name": "summary", "type": "STRING", "required": False},
        },
        "cypher": "title_acquisition_v1.j2",
        "fact_descriptor": {
            "predicate": "HAS_TITLE",
            "subject": "$character",
            "value": "$title_name",
            "object": "$title_name",
        },
    },
]


# ===== ./services/slot_filler.py =====
"""
app/services/slot_filler.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Компонент SlotFiller ― «клей» между текстом и CypherTemplate.

• Получает текст + CypherTemplate
• Прогоняет 3 фазы (extract → fallback → generate)
• Возвращает **список** заполнений вида
  {
    "template_id": "...",
    "slots": {...},       # готово для template.render()
    "details": "chain-of-thought"
  }

Использует:
  – LangChain + OpenAI (Structured JSON)
  – Jinja2 для промптов (app/prompts/*.j2)
  – Pydantic для строгой валидации
  – (опц.) Langfuse для трассировки

Шаблоны-промпты ожидают переменные:
  • template      (CypherTemplate, нужен description и др.)
  • text          (сырой фрагмент)
  • slots         (List[SlotDefinition])
  • slot_names    (List[str])
  • previous      (список объектов из прошлой фазы)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import langfuse
import openai
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, ValidationError, create_model, RootModel

from core.slots.prompts import PROMPTS_ENV
from schemas.cypher import CypherTemplate
from utils.logger import get_logger


logger = get_logger(__name__)



# Преобразование строковых типов из SlotDefinition → реальные Python-типы
TYPE_MAP = {
    "STRING": str,
    "INT": int,
    "FLOAT": float,
    "BOOL": bool,
}

from pydantic import BaseModel, Field
from typing import Optional, List

def build_slot_model(template: CypherTemplate) -> type[BaseModel]:
    fields = {
        slot.name: (TYPE_MAP[slot.type], Field(description=slot.description or "..."))
        for slot in template.slots.values()
    }
    fields["details"] = (str, Field(description="Как извлечены значения"))
    return create_model("ResponseItem", **fields)

# ──────────────────────────────────────────────────────────────────────────────
# SlotFiller
# ──────────────────────────────────────────────────────────────────────────────
class SlotFiller:
    """Класс, извлекающий / дополняющий значения слотов с помощью LLM."""

    # ------------------------------------------------------------------ init --
    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.2,
        langfuse_client: Optional[langfuse.Langfuse] = None,
    ):
        """
        Parameters
        ----------
        api_key : str
            OpenAI API-ключ.
        model_name : str
            Название модели (по умолчанию gpt-4o-mini).
        temperature : float
            Температура для LLM (низкая, чтобы быть детерминированным).
        langfuse_client : Optional[langfuse.Langfuse]
            Необязательный клиент Langfuse для трассировки.
        """
        openai.api_key = api_key
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            openai_api_key=api_key,
        )
        self.tracer = langfuse_client

    def fill_slots(self, template: CypherTemplate, text: str) -> List[Dict[str, Any]]:
        """
        Главный метод, вызываемый из ExtractionPipeline.

        Returns
        -------
        List[Dict[str, Any]]
            Список заполнений (может быть пустым).
        """
        fillings = self._run_phase(
            phase="extract",
            prompt_file="extract_slots.j2",
            template=template,
            text=text,
        )

        if self._needs_fallback(fillings, template):
            fillings = self._run_phase(
                phase="fallback",
                prompt_file="fallback_slots.j2",
                template=template,
                text=text,
                previous=fillings,
            )

        fillings = self._run_phase(
            phase="generate",
            prompt_file="generate_slots.j2",
            template=template,
            text=text,
            previous=fillings,
        )

        validated: List[Dict[str, Any]] = []
        for item in fillings:
            try:
                validated.append(
                    {
                        "template_id": template.id,
                        "slots": self._validate_and_cast(item, template),
                        "details": item.get("details", ""),
                    }
                )
            except (ValueError, ValidationError):
                # Пропускаем невалидный объект, но можно логировать
                continue

        return validated

    def _run_phase(
        self,
        phase: str,
        prompt_file: str,
        template: CypherTemplate,
        text: str,
        previous: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Общий метод для трёх фаз (extract / fallback / generate).
        """
        if phase != "extract" and not self._needs_fallback(previous, template):
            return previous or []

        slot_names = [s.name for s in template.slots.values()]

        ItemModel = build_slot_model(template)

        # 2. Обёртка для списка
        class ResponseList(RootModel[List[ItemModel]]):
            pass

        parser = PydanticOutputParser(pydantic_object=ResponseList)
        format_instructions = parser.get_format_instructions()

        # 2. Рендерим Jinja-промпт
        tpl = PROMPTS_ENV.get_template(prompt_file)
        rendered = tpl.render(
            template=template,
            text=text,
            slots=template.slots.values(),
            slot_names=slot_names,
            previous=previous,
        )

        # 3. Создаём LangChain Prompt
        prompt = PromptTemplate(
            template=rendered + "\n\n{format_instructions}",
            input_variables=["format_instructions"],
            partial_variables={"format_instructions": format_instructions},
        )

        chain = prompt | self.llm | parser

        # 4. Запускаем цепочку с Langfuse
        span = self.tracer.span(name=f"slotfiller.{phase}") if self.tracer else None
        try:
            result = chain.invoke({})
        except Exception:
            try:
                result = chain.invoke({})
            except Exception as e:
                logger.error(f"Error in phase {phase}: {str(e)}")
                raise
        finally:
            if span:
                span.end()
    
        return result.model_dump()

    @staticmethod
    def _needs_fallback(
        fillings: Optional[List[Dict[str, Any]]], template: CypherTemplate
    ) -> bool:
        """True, если хотя бы один объект не содержит всех обязательных слотов."""
        if not fillings:
            return True
        required = {s.name for s in template.slots.values() if s.required}
        for obj in fillings:
            if not required.issubset(obj.keys()):
                return True
        return False

    def _validate_and_cast(
        self, obj: Dict[str, Any], template: CypherTemplate
    ) -> Dict[str, Any]:
        """
        Строго валидирует объект через динамическую Pydantic-модель
        и приводит типы согласно SlotDefinition.type.
        """
        # 1) строим динамическую Pydantic-схему
        fields = {
            s.name: (TYPE_MAP[s.type], ... if s.required else None)
            for s in template.slots.values()
        }
        DynamicModel: type[BaseModel] = create_model("DynamicSlotsModel", **fields)  # type: ignore

        # 2) фильтруем только нужные ключи (лишние игнорируем)
        filtered = {k: obj.get(k) for k in fields.keys() if k in obj}

        # 3) валидация + автоматический каст типов
        validated: BaseModel = DynamicModel(**filtered)
        return validated.model_dump()


# ===== ./services/graph_proxy.py =====
from __future__ import annotations

"""GraphProxy — thin convenience wrapper around the official Neo4j Python
   driver.  It provides single-query and batched execution helpers with
   automatic retry semantics, read/write separation, and optional debug
   logging controlled by `app_settings.DEBUG`.
"""

from contextlib import AbstractContextManager
from typing import Any, Dict, Iterable, List, Optional

from neo4j import Driver, GraphDatabase, Transaction

from config import app_settings

__all__ = ["GraphProxy"]


class GraphProxy(AbstractContextManager):
    """Communicates with Neo4j (see README §2 «GRAPH_PROXY»).

    Notes
    -----
    * Uses *transaction functions* (`execute_read` / `execute_write`) so the
      driver can transparently retry transient failures (e.g. leader switch).
    * Supports *batched* execution of several Cypher statements inside a single
      transaction (`run_queries`).
    * Provides a minimal context-manager interface allowing ``with`` usage.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str | None = None,
    ) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _run(
        tx: Transaction, cypher: str, params: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:  # noqa: E501
        """Internal helper executed inside a transaction function."""
        result = tx.run(cypher, params or {})
        return [record.data() for record in result]

    def _log(self, cypher: str, params: Optional[Dict[str, Any]]) -> None:
        if app_settings.DEBUG:
            print(">>> CYPHER", "\n", cypher, "\nPARAMS =", params, "\n<<<")

    # ----------------------------------------------------------- public api --
    def run_query(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        write: bool = True,
    ) -> List[Dict[str, Any]]:
        """Execute a *single* Cypher statement and return list[dict].

        Parameters
        ----------
        cypher : str
            The Cypher query string.
        params : dict | None, optional
            Parameters bound to the query.
        write : bool, default ``True``
            If ``False`` the statement is routed to a *read* replica.
        """
        self._log(cypher, params)
        with self._driver.session(database=self._database) as session:
            fn = session.execute_write if write else session.execute_read
            return fn(self._run, cypher, params)

    def run_queries(
        self,
        cyphers: Iterable[str],
        params_list: Optional[Iterable[Optional[Dict[str, Any]]]] = None,
        *,
        write: bool = True,
    ) -> List[Dict[str, Any]]:
        """Execute *multiple* Cypher statements in a single transaction.

        All statements are executed sequentially; if any fails the entire
        transaction is rolled back.  ``params_list`` must be the same length
        as ``cyphers`` or ``None`` (⇢ no parameters).
        """
        cypher_list = list(cyphers)
        params_list = list(params_list or [None] * len(cypher_list))
        if len(cypher_list) != len(params_list):
            raise ValueError("params_list length mismatch with cyphers")

        def batch_tx(tx: Transaction) -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []
            for c, p in zip(cypher_list, params_list):
                self._log(c, p)
                results.extend(self._run(tx, c, p))
            return results

        with self._driver.session(database=self._database) as session:
            fn = session.execute_write if write else session.execute_read
            return fn(batch_tx)

    # -------------------------------------------------------------- cleanup --
    def close(self) -> None:  # noqa: D401
        """Close underlying driver (call at application shutdown)."""
        self._driver.close()

    # -------------------------------------------------------- context-manager --
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401
        self.close()


# ===== ./services/pipeline.py =====
from typing import Tuple, List, Dict, Any

from services.graph_proxy import GraphProxy
from services.slot_filler import SlotFiller
from services.templates import TemplateService
from schemas.cypher import CypherTemplate


class ExtractionPipeline:
    """Связывает TemplateService → SlotFiller → GraphProxy."""

    def __init__(
        self,
        template_service: TemplateService,
        slot_filler: SlotFiller,
        graph_proxy: GraphProxy,
        top_k: int = 3,
    ):
        self.template_service = template_service
        self.slot_filler = slot_filler
        self.graph_proxy = graph_proxy
        self.top_k = top_k

    def extract_and_save(
        self, text: str, chapter: int, tags: List[str] | None = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        templates = self.template_service.top_k(text, k=self.top_k)
        all_facts = []
        inserted_ids = []

        for tpl in templates:
            slot_sets = self.slot_filler.fill_slots(tpl, text)
            for slot_data in slot_sets:
                slots = slot_data["slots"]

                cypher = _render_cypher(tpl, slots, chapter, tags)
                result = self.graph_proxy.run_query(cypher)

                all_facts.append(
                    {
                        "template": tpl.id,
                        "slots": slots,
                        "details": slot_data.get("details", ""),
                    }
                )
                inserted_ids.extend([r.get("id") for r in result if "id" in r])

        return all_facts, inserted_ids


def _render_cypher(
    template: CypherTemplate,
    slots: Dict,
    chapter: int,
    tags: List[str] | None,
) -> str:
    """Рендерит финальный Cypher Jinja2-шаблон."""

    context = dict(slots)
    context.update(
        {
            "chapter": chapter,
            "tags": tags or [],
        }
    )

    if template.fact_descriptor:
        fd = template.fact_descriptor

        def resolve(expr: str | None) -> str | None:
            if expr and expr.startswith("$"):
                return slots.get(expr[1:])
            return expr

        context["fact"] = {
            "predicate": fd.predicate,
            "subject": resolve(fd.subject),
            "object": resolve(fd.object),
            "value": resolve(fd.value),
        }

    return template.render(slots=context)


# ===== ./services/templates/service.py =====
from services.templates import TemplateService
from config import app_settings
from config.weaviate import connect_to_weaviate
from config.embeddings import openai_embedder


weaviate_client = connect_to_weaviate(
    url=app_settings.WEAVIATE_URL,
    api_key=app_settings.WEAVIATE_API_KEY,
)

template_service = TemplateService(
    weaviate_client=weaviate_client, embedder=openai_embedder
)


# ===== ./services/templates/__init__.py =====
from __future__ import annotations
from uuid import uuid4

from services.templates.warning import log_low_score_warning

"""TemplateService — high‑level helper around Weaviate that stores and retrieves
CypherTemplate objects.

"""

from typing import Callable, List, Optional, Sequence, Dict, Any
import os

import weaviate
from weaviate.exceptions import UnexpectedStatusCodeException
import weaviate.classes as wvc
from weaviate.classes.config import Configure
from weaviate.classes.query import Filter
from weaviate.collections.classes.internal import ObjectSingleReturn
from weaviate.classes.query import MetadataQuery

from schemas.cypher import (
    CypherTemplate,
    CypherTemplateBase,
    SlotDefinition,
    FactDescriptor,
)  # noqa: F401

EmbedderFn = Callable[[str], List[float]]  # opaque function → 1536‑d vector


class TemplateService:
    CLASS_NAME = "CypherTemplate"

    def __init__(
        self,
        weaviate_client: Optional[weaviate.Client] = None,
        embedder: Optional[EmbedderFn] = None,
    ) -> None:
        """Create the service.

        Parameters
        ----------
        weaviate_client
            Weaviate client to use.
        embedder
            Optional callable that takes raw text and returns an embedding
            vector. If *None* the service falls back to ``nearText`` search.
        """

        self.client: weaviate.Client = weaviate_client

        self.embedder = embedder
        self._ensure_schema()

    def upsert(self, tpl: CypherTemplateBase) -> None:
        """Create *or* update a template in Weaviate.

        * If the object exists → do a *PATCH* update.
        * If not → create it (vector supplied if present or computable).
        """
        # Формируем payload без uuid
        payload: Dict[str, Any] = tpl.model_dump(
            mode="json", exclude_none=True, exclude={"uuid"}
        )

        # Добавляем вектор при необходимости
        if payload.get("vector") is None and self.embedder:
            payload["vector"] = self.embedder(self._canonicalise_template(tpl))  # type: ignore[arg-type]

        coll = self.client.collections.get(self.CLASS_NAME)

        # Ищем существующий объект по полю 'name'
        existing = coll.query.fetch_objects(
            filters=Filter.by_property("name").equal(tpl.name), limit=1
        ).objects

        if existing:
            # Обновляем существующий объект
            uuid = existing[0].uuid
            coll.data.update(
                uuid=uuid, properties=payload, vector=payload.get("vector")
            )
        else:
            # Вставляем новый объект и получаем его UUID
            uuid = getattr(tpl, "uuid", None) or str(uuid4())
            uuid = coll.data.insert(
                properties=payload, uuid=uuid, vector=payload.get("vector")
            )

        return CypherTemplate(id=uuid, **payload)  # type: ignore[arg-type]

    def get(self, id: str) -> CypherTemplate:
        coll = self.client.collections.get(self.CLASS_NAME)
        obj = coll.query.fetch_object_by_id(id)
        if not obj:
            raise ValueError(f"Template {id} not found")
        return self._from_weaviate(obj)

    def get_by_name(self, name: str) -> CypherTemplate:
        coll = self.client.collections.get(self.CLASS_NAME)
        res = coll.query.fetch_objects(
            filters=Filter.by_property("name").equal(name), limit=1
        ).objects
        if not res:
            raise ValueError(f"Template '{name}' not found")
        return self._from_weaviate(res[0])

    def top_k(
        self,
        query: str,
        category: Optional[str] = None,
        k: int = 3,
        distance_threshold: float = 0.5,
    ) -> List[CypherTemplate]:
        """Semantic search for the *k* best‑matching templates.

        The method performs an **HNSW vector search** if an embedder is
        configured; otherwise it uses Weaviate's ``nearText`` fallback which is
        less precise but still acceptable for local dev.
        """
        if k <= 0:
            return []

        coll = self.client.collections.get(self.CLASS_NAME)

        # Определяем фильтры, если указана категория
        filters = Filter.by_property("category").equal(category) if category else None

        # Выполняем поиск по вектору или по тексту
        if self.embedder:
            vector = self.embedder(query)
            results = coll.query.near_vector(
                near_vector=vector,
                limit=k,
                filters=filters,
                return_metadata=MetadataQuery(score=True, distance=True),
            )
        else:
            results = coll.query.near_text(
                query=query,
                limit=k,
                filters=filters,
                return_metadata=MetadataQuery(score=True, distance=True),
            )

        if not results.objects:
            return []

        objects = results.objects
        distances = [obj.metadata.distance for obj in objects]

        if distances and distances[0] > distance_threshold:
            log_low_score_warning(query, objects, distances, distance_threshold)

        return [self._from_weaviate(obj) for obj in objects]

    def _ensure_schema(self) -> None:
        if self.client.collections.exists(self.CLASS_NAME):
            return

        self.client.collections.create(
            name=self.CLASS_NAME,
            description="Template that maps narrative text to Cypher code and optional Fact creation.",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            inverted_index_config=Configure.inverted_index(index_property_length=True),
            properties=[
                wvc.config.Property(name="name", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="version", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="description", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(name="details", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="category", data_type=wvc.config.DataType.TEXT
                ),
                wvc.config.Property(
                    name="slots",
                    data_type=wvc.config.DataType.OBJECT,
                    nested_properties=[
                        wvc.config.Property(
                            name="type", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="description", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="required", data_type=wvc.config.DataType.BOOL
                        ),
                        wvc.config.Property(
                            name="default", data_type=wvc.config.DataType.TEXT
                        ),
                    ],
                ),
                wvc.config.Property(name="cypher", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="fact_descriptor",
                    data_type=wvc.config.DataType.OBJECT,
                    nested_properties=[
                        wvc.config.Property(
                            name="predicate", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="subject", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="value", data_type=wvc.config.DataType.TEXT
                        ),
                        wvc.config.Property(
                            name="object", data_type=wvc.config.DataType.TEXT
                        ),
                    ],
                ),
                wvc.config.Property(name="author", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(
                    name="created_at", data_type=wvc.config.DataType.DATE
                ),
                wvc.config.Property(
                    name="updated_at", data_type=wvc.config.DataType.DATE
                ),
            ],
        )

    @staticmethod
    def _canonicalise_template(tpl: CypherTemplateBase) -> str:
        """Return a **stable** string representation that feeds the embedder.

        The canonical form concatenates the key semantic elements separated by
        `‖` (U+2016) so that small field order changes do not alter the meaning.
        """
        representation = tpl.description
        if tpl.details:
            representation += " ‖ " + tpl.details

        return representation

    @staticmethod
    def _from_weaviate(raw: ObjectSingleReturn) -> CypherTemplate:
        props = raw.properties
        allowed = {
            "name",
            "version",
            "title",
            "description",
            "details",
            "category",
            "slots",
            "cypher",
            "fact_descriptor",
            "author",
            "created_at",
            "updated_at",
            "vector",
        }
        clean = {k: v for k, v in props.items() if k in allowed}
        clean["id"] = str(raw.uuid)
        return CypherTemplate(**clean)


# ===== ./services/templates/warning.py =====
from schemas.cypher import CypherTemplate


def log_low_score_warning(
    query: str, templates: list[CypherTemplate], scores: list[float], threshold: float
) -> None:
    """
    Логирует предупреждение, если скор топ‑результата ниже порогового.

    Parameters
    ----------
    query : str
        Исходный запрос.
    templates : List[CypherTemplate]
        Список найденных темплейтов.
    scores : List[float]
        Список скорoв, соответствующих найденным темплейтам.
    threshold : float
        Пороговый скор.
    """
    print("⚠️ Warning: top result score below threshold!")
    print(f"Query: {query}")
    print("Results:")
    for template, score in zip(templates, scores):
        print(f"- {template.properties['name']} (score: {score:.4f})")


