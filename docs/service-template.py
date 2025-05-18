# =============================================================================
# 📁 app/config/settings.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Загружает конфигурацию приложения из `.env` при помощи pydantic‑settings
#  • Значения нужны всем компонентам: ключи API, строки подключения, токен auth
#  • Полностью соответствует разделу «🔐 Авторизация» и таблицам интеграций
#    (Neo4j, Weaviate, OpenAI, Langfuse) в specification.md
# =============================================================================

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
    WEAVIATE_URL: str  # Weaviate (TemplateService)
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


# =============================================================================
# 📁 app/core/auth.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Реализует простую Bearer‑авторизацию, описанную в spec («используйте
#    FastAPI Depends»).
#  • Используется на всех защищённых энд‑пойнтах.
# =============================================================================

from fastapi import Depends, Header, HTTPException, status


def get_token_header(authorization: str = Header(...)) -> str:
    """Проверяет Bearer‑токен из заголовка Authorization."""
    token = authorization.replace("Bearer ", "")
    if token != app_settings.AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return token


# =============================================================================
# 📁 app/schemas/extract.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Pydantic‑модели запросов/ответов для `/v1/extract-save`
#  • Поля соответствуют разделу «Основной функционал / extract-save»
# =============================================================================

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


# =============================================================================
# 📁 app/services/graph_proxy.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Обёртка над Neo4j Python‑драйвером
#  • Выполняет Cypher‑запросы, логирует при DEBUG, пробрасывает ошибки
# =============================================================================

from typing import Any, Dict, List
from neo4j import GraphDatabase, Driver


class GraphProxy:
    """Коммуницирует с Neo4j (см. README §2 «GRAPH_PROXY»)."""

    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def run_query(self, cypher: str, params: Dict[str, Any] | None = None) -> List:
        """Выполняет Cypher и возвращает список записей."""
        if app_settings.DEBUG:
            print(">>> CYPHER\n", cypher, "\n<<<")

        with self._driver.session() as session:
            result = session.run(cypher, params or {})
            return [r.data() for r in result]


# =============================================================================
# 📁 app/services/template_service.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Поиск `CypherTemplate` в Weaviate по векторной близости
#  • Соответствует компоненту TemplateService в spec/README
# =============================================================================

import requests
from typing import List, Dict



class TemplateService:
    def __init__(self):
        self._data: dict[str, CypherTemplate] = {}

    def upsert(self, tpl: CypherTemplate):
        self._data[tpl.id] = tpl

    def get(self, tpl_id: str) -> CypherTemplate:
        return self._data[tpl_id]

    def top_k(self, query: str, group: str | None = None, k: int = 3):
        items = [t for t in self._data.values() if group is None or t.category == group]
        return items[:k]


# =============================================================================
# 📁 app/services/slot_filler.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Заполняет slot_schema шаблона через LLM
#  • Поддерживает три режима из README §6: extract, fallback, generate
# =============================================================================

import openai


class SlotFiller:
    """LLM‑клиент, отвечающий за заполнение слотов."""

    def __init__(self, api_key: str):
        openai.api_key = api_key

    def fill_slots(self, template: Dict, text: str) -> Dict:
        """Возвращает dict с заполненными slot‑ами.

        Сейчас упрощённый мок. В рабочей версии:
        1) промптируем модель на строгий JSON‑ответ;
        2) валидируем по slot_schema;
        3) делаем fallback / generative при нехватке данных.
        """
        schema = template.get("slot_schema", {})
        # --- MOCK ----------------------------------------------------------------
        if "character" in schema and "faction" in schema:
            return {"character": "Арен", "faction": "Северный фронт"}
        # -------------------------------------------------------------------------
        return {k: f"mock_{k}" for k in schema.keys()}


# =============================================================================
# 📁 app/services/extraction.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Реализует ExtractionPipeline, шаг за шагом из README §3
#  • На выходе — факты + ID вставленных сущностей
# =============================================================================

from typing import Tuple, List, Dict, Any


class ExtractionPipeline:
    """Связывает TemplateService → SlotFiller → GraphProxy."""

    def __init__(
        self,
        template_service: TemplateService,
        slot_filler: SlotFiller,
        graph_proxy: GraphProxy,
    ):
        self.template_service = template_service
        self.slot_filler = slot_filler
        self.graph_proxy = graph_proxy

    # --- публичный метод -------------------------------------------------------
    def run(
        self, text: str, chapter: int, tags: List[str] | None = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Главный метод энд‑пойнта `/v1/extract-save`.

        Возвращает:
        • facts — список dict‑ов (лог, пригодно для отладки или UI)
        • inserted_ids — ID созданных узлов/фактов
        """
        templates = self.template_service.find_templates(text)
        all_facts: List[Dict] = []
        inserted: List[str] = []

        for tpl in templates:
            # 1. Заполняем слоты
            slots = self.slot_filler.fill_slots(tpl, text)
            # 2. Рендерим Cypher (пока — псевдо)
            cypher = self._render_cypher(tpl, slots, chapter, tags)
            # 3. Сохраняем в граф
            result = self.graph_proxy.run_query(cypher)
            # 4. Агрегируем результаты
            all_facts.append({"template": tpl["id"], "slots": slots})
            inserted.extend([r.get("id") for r in result if "id" in r])

        return all_facts, inserted

    # --- приватные утилиты ------------------------------------------------------
    def _render_cypher(
        self,
        template: Dict,
        slots: Dict,
        chapter: int,
        tags: List[str] | None,
    ) -> str:
        """Подставляет слоты в Cypher Jinja2‑шаблон.

        🎯 В проде используем Jinja2 – см. utils/jinja.py.
        """
        return f"// Cypher for template={template['id']} slots={slots}"


# =============================================================================
# 📁 app/core/router.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Собирает зависимости и регистрирует все маршруты
#    → /v1/extract-save  (добавить позже /v1/augment-context)
# =============================================================================

from fastapi import FastAPI, Depends
from app.schemas.extract import ExtractRequest, ExtractResponse

app = FastAPI(
    title="StoryGraph API",
    description=(
        "Backend‑сервис для извлечения и версионирования фактов из повествования. "
        "См. README.md и specification.md."
    ),
    version="0.1.0",
)

# === DI‑singletons (создаём один раз) ========================================
template_service = TemplateService(app_settings.WEAVIATE_URL)
slot_filler = SlotFiller(app_settings.OPENAI_API_KEY)
graph_proxy = GraphProxy(
    app_settings.NEO4J_URI, app_settings.NEO4J_USER, app_settings.NEO4J_PASSWORD
)
extraction_pipeline = ExtractionPipeline(template_service, slot_filler, graph_proxy)


# === Endpoints ===============================================================
@app.post("/v1/extract-save", response_model=ExtractResponse)
def extract_save(
    request: ExtractRequest,
    _: str = Depends(get_token_header),
) -> ExtractResponse:
    """Маршрут соответствует spec «/v1/extract-save».

    ↗  orchestrates: TemplateService → SlotFiller → GraphProxy
    ↘  returns: список фактов + ID вставок
    """
    facts, ids = extraction_pipeline.extract_and_save(
        request.text, request.chapter, request.tags
    )
    return ExtractResponse(facts=facts, inserted_ids=ids)


# =============================================================================
# 📁 app/main.py
# -----------------------------------------------------------------------------
# Назначение
# ----------
#  • Точка входа Uvicorn. Просто импортируем `app` из router.
# =============================================================================

from app.core.router import app  # noqa: F401  (re‑export for Uvicorn)


# =============================================================================
# 📄 Dockerfile  (корень проекта)
# -----------------------------------------------------------------------------
# Краткая аннотация
# -----------------
#  • Базируется на python:3.11‑slim
#  • Кэшируется requirements.txt
#  • Запускает Uvicorn
# =============================================================================

"""
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""


# =============================================================================
# 📄 docker-compose.yml  (корень проекта)
# -----------------------------------------------------------------------------
# Краткая аннотация
# -----------------
#  • Поднимает контейнер StoryGraph
#  • Прокидывает порт 8000
#  • Использует .env для секретов
# =============================================================================

"""
version: "3.9"
services:
  storygraph:
    build: .
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - .:/app
"""


# =============================================================================
# 📄 .env  (пример, корень)
# -----------------------------------------------------------------------------
# Содержит чувствительные данные; **не** коммитить в публичный репозиторий.
# =============================================================================

"""
OPENAI_API_KEY=sk-*************
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=pass
WEAVIATE_URL=http://weaviate:8080
AUTH_TOKEN=super-secret-token
DEBUG=true
"""
