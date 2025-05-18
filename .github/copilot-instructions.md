# 🧠 Инструкции для GitHub Copilot

## 📌 Общие принципы
- Используй **FastAPI** как веб-фреймворк.
- Везде используй `async def` и `await`, кроме мест, где явно синхронный клиент.
- Используй **Pydantic** для всех моделей запросов и ответов.
- Соблюдай структуру проекта:
  - `app/api/` - FastAPI роуты, эндпоинты приложения
  - `app/services/` — бизнес-логика (TemplateService, SlotFiller, GraphProxy)
  - `app/schemas/` — схемы Pydantic (по папкам: extract.py, augment.py и т.д.)
  - `app/config/` — настройки, подключение внешних клиентов, auth
  - `app/core/` — core логика приложения
  - `app/utils/` — шаблонизация (Jinja2), логирование, хелперы
- Не дублируй импорты между слоями; соблюдай SRP.

## 🔐 Авторизация
- Все защищённые эндпоинты используют `Depends(get_token_header)`.
- Токен берётся из `Authorization: Bearer ...` и сверяется с `app_settings.AUTH_TOKEN`.

## ⚙️ Инфраструктура и зависимости
- Используй `GraphProxy` для всех запросов к Neo4j.
- Используй `TemplateService` для поиска Cypher-шаблонов в Weaviate.
- Используй `SlotFiller` (через OpenAI) для заполнения `slot_schema`.
- Сборку оркестрации реализует `ExtractionPipeline`.

## 🧠 LLM и шаблоны
- Слоты подставляются в Jinja2-шаблоны (`versioned_fact.j2`) перед отправкой в Neo4j.
- Шаблоны берутся из Weaviate и содержат `slot_schema`, `fact_type`, `fact_policy`, `fact_value_slot`.
- При `fact_policy=auto` — факт сохраняется, если так решает модель.
- Не генерируй шаблоны «с нуля» — используем существующие из Weaviate.

## 📊 Логирование и отладка
- При `DEBUG=true`, все Cypher-запросы логируются через `print`.
- Для трассировки запросов LLM используется Langfuse.

## 🧪 Тестирование
- Для API-тестов используй `pytest` и `httpx.AsyncClient`.
- Все фикстуры хранятся в `app/tests/conftest.py`.

## 📂 Стандарты
- Стиль — `PEP8`, форматирование — `black`.
- Все функции с аннотацией типов.
- Используй f-строки вместо `format()`.
- Все модели должны содержать `description=` в `Field(...)`.

## 📝 Спецификация API
- Реализованы 2 эндпоинта:
  - `/v1/extract-save`: извлечение фактов
  - `/v1/augment-context`: сбор релевантного контекста (см. `AugmentPipeline`, TODO)

## 🧩 Примеры полезных ссылок
- Структура репозитория: `#file:docs/service_structure.md`
- Спецификация API: `#file:docs/specification.md`
- Шаблон сервиса 1 итерация: `#file:docs/service-template.py`
