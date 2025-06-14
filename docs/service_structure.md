# 📦 Структура проекта StoryGraph

Этот документ описывает структуру директорий и файлов проекта **StoryGraph**, включая их назначение и рекомендации по использованию.

---

## 🗂️ Корневая структура

```
.
├── .env
├── Dockerfile
├── docker-compose.yml
├── README.md
├── docs/
└── app/
    ├── __init__.py
    ├── main.py
    ├── config/
    │   ├── __init__.py
    │   ├── settings.py
    │   └── clients/
    ├── api/
    ├── core/
    ├── services/
    ├── schemas/
    ├── utils/
    └── tests/
```

---

## 📁 Корень проекта

| Файл                  | Назначение |
|-----------------------|------------|
| `.env`                | Переменные окружения, включая ключи и токены. Не публикуется. |
| `Dockerfile`          | Описание контейнера для запуска FastAPI-приложения. |
| `docker-compose.yml`  | Сценарий запуска сервиса и его зависимостей (Weaviate, Neo4j). |
| `README.md`           | Документация и инструкции по использованию. |

---

## 📁 app/

Главная директория Python-кода.

### `main.py`

- Точка входа в приложение.
- Импортирует `FastAPI` объект из `core/router.py`.

---

## 📁 app/config/

Настройки приложения и клиенты внешних сервисов.

### `settings.py`

- Загружает переменные из `.env` через `pydantic_settings.BaseSettings`.
- Настройки подключения к OpenAI, Neo4j, Weaviate, Langfuse и токен авторизации.

- `openai.py` — клиент для OpenAI API.
- `neo4j.py` — подключение и драйвер Neo4j.
- `weaviate.py` — интерфейс для Weaviate API.
- `langfuse.py` — трассировка LLM-запросов (если нужно).

---

## 📁 app/core/

Основная инфраструктура.

- `auth.py` — проверка Bearer-токена в запросе.
- `router.py` — инициализация FastAPI и всех маршрутов.

---

## 📁 app/services/

Реализация бизнес-логики.

- `extraction.py` — Pipeline `extract-save`.
- `pipeline.py` — пайплайны `extract-save` и `augment-context`.
- `template_service.py` — Поиск шаблонов через Weaviate.
- `slot_filler.py` — Извлечение слотов из текста через LLM.
- `graph_proxy.py` — Работа с Neo4j и выполнение Cypher-запросов.

---

## 📁 app/schemas/

Модели данных для валидации запросов и ответов (Pydantic).

- `extract.py` — схемы для `/v1/extract-save`.
- `template.py` — схемы шаблонов `CypherTemplate`.

---

## 📁 app/utils/

Утилиты и вспомогательные функции.

- `jinja.py` — рендеринг шаблонов Jinja2.
- `logger.py` — централизованное логирование.
- `helpers.py` — общие инструменты (например, генерация UUID, даты).

---

## 📁 app/tests/

Тесты (unit + интеграционные).

- `test_extraction.py` — тесты `extract-save`.
- `test_augmentation.py` — тесты `augment-context`.
- `test_templates.py` — поведение шаблонов.
- `conftest.py` — фикстуры и общий setup.

---

## 🧩 Примечания

- Все компоненты и слои описаны в `README.md` и сопутствующих документах.
- Версионирование реализуется через `ChunkNode` и `RaptorNode`, без отдельной сущности `Fact`.
- Все данные хранятся в графовой БД Neo4j.