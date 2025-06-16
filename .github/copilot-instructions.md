# 🧠 Инструкции для GitHub Copilot

Этот файл задаёт контекст для автодополнения кода. Он описывает текущую
архитектуру сервиса StoryGraph. Ранее документация ссылалась на сущность `Fact`,
но теперь истории версионируются через связку `ChunkNode` и `RaptorNode`.
Уточнённые инструкции помогают Copilot сразу предлагать решения в рамках новой
модели.

## 📌 Общие принципы
- Используй **FastAPI** как веб-фреймворк.
- Везде используй `async def` и `await`, кроме мест, где явно синхронный клиент.
- Используй **Pydantic** для всех моделей запросов и ответов.
- Соблюдай структуру проекта:
  - `app/api/` — FastAPI роуты (extract, augment)
  - `app/services/` — бизнес‑логика (TemplateService, SlotFiller, GraphProxy и др.)
  - `app/schemas/` — Pydantic‑схемы (extract.py, augment.py, template.py)
  - `app/config/` — настройки и клиенты внешних сервисов
  - `app/core/` — общая инфраструктура и auth
  - `app/utils/` — шаблоны Jinja2, логирование, helpers
  - `app/templates/` — базовые Jinja2‑шаблоны для графовых операций
  - `app/tests/` — unit и интеграционные тесты
  - `main.py` — точка входа в приложение
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
- Слоты подставляются в доменный Jinja2-шаблон, при необходимости обёрнутый в `base_fact.j2`.
- Шаблоны из Weaviate содержат `slot_schema`, `graph_relation`, `fact_policy`, `attachment_policy`.
- `fact_policy` регулирует сохранение результата (`none` или `always`).
- После коммита Cypher `FlatRaptorIndex` возвращает `raptor_node_id` для `ChunkNode`.
- Не генерируй шаблоны «с нуля» — используем существующие из Weaviate.

## 📊 Логирование и отладка
- Подключай логгер через `from app.utils.logger import get_logger` и используй `logger = get_logger(__name__)`.
- При `DEBUG=true` все Cypher-запросы пишутся в лог вместо `print`.
- Для трассировки запросов LLM используется Langfuse.

## Тестирование

- Запуск всех тестов: `pytest -q`
- Общие фикстуры (включая `event_loop`) находятся в `app/tests/conftest.py`

### Структура

Тесты строго зеркально повторяют структуру `app/`, чтобы можно было однозначно определить, где лежат тесты для каждого компонента:

```
app/services/pipeline.py
→ app/tests/unit/services/pipeline/test_pipeline_.py
→ app/tests/integration/services/pipeline/test_pipeline_.py
```

### Юнит-тесты

- Располагаются в `app/tests/unit/...`
- Изолированы от внешних сервисов: БД, LLM, эмбеддинги
- Используют мок-объекты и фикстуры из `conftest.py`
- Не обращаются к переменным окружения или сетевым ресурсам

### Интеграционные тесты

- Располагаются в `app/tests/integration/...`
- Требуют реальные ключи (OpenAI, Weaviate и др.)
- При их отсутствии тесты помечаются как `skipped`

### Практика TDD

При добавлении нового класса или функции сразу создавайте минимальные юнит-тесты в соответствующей зеркальной директории. Структура кода и тестов должна оставаться синхронизированной.

### Best Practices для pytest (юнит-тесты)

- Используйте для переиспользуемой подготовки данных и окружения. Общие — в conftest.py.
- Тесты независимы, без сохранения состояния.
- Названия описывают поведение: test_get_user_returns_404.
- Без дублирования:Общую логику — в фикстуры или хелперы.
- Используйте @pytest.mark.parametrize для разных входов.
- Один тест — одна проверка. Лучше больше, но простых.


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
- Структура репозитория: `#file:docs/components/service_structure.md`
- Обзор пайплайна: `#file:docs/pipelines/pipeline_overview.md`
- Pydantic модели шаблонов: `#file:docs/models/pydantic_models_for_cypher_template.md`
- Архитектура Raptor: `#file:docs/pipelines/raptor_pipeline_architecture.md`
