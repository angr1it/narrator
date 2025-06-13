# AGENTS.md

Основные правила работы с репозиторием. Глубже расположенные `AGENTS.md` переопределяют эти инструкции.

## Структура проекта
- `app/api` — FastAPI роуты
- `app/services` — бизнес-логика
- `app/schemas` — Pydantic-модели
- `app/config` — клиенты внешних сервисов
- `app/core` — авторизация и общие компоненты
- `app/utils` — логгер и хелперы
- `app/templates` — Jinja2-шаблоны
- `app/tests` — тесты
- `docs/` — документация
- `app/main.py` — точка входа

## Код-стайл
- PEP8 и аннотации типов
- Форматирование — `black`
- Линтер — `flake8`
- Используйте f-строки
- В `Field()` указывайте `description`
- Для логирования применяйте `get_logger` из `app.utils.logger`

## Локальная разработка
- Создайте `.env` на основе примера
- Запустите API: `docker compose up -d`
- Для интеграционных тестов дополнительно запустите зависимости:
  `docker compose --profile integration up -d`
- Проверьте Weaviate: `curl http://localhost:8080/v1/meta`

## Тестирование
- Запуск тестов: `pytest -q`
- Запуск с покрытием: `pytest --cov=app --cov-report=xml:coverage.xml --cov-report=html --cov-fail-under=85 -q`
- Подробности — в `app/tests/AGENTS.md`

## Pull request
- Заголовок — короткий глагол
- Описание содержит `## Summary` и `## Testing`

## Обязательные проверки
- `black --check .`
- `flake8`
- `mypy .`
- `pytest --cov=app --cov-report=xml:coverage.xml --cov-report=html --cov-fail-under=85 -q`

### Pre-commit
- После установки зависимостей выполните `pre-commit install`
- Хуки запускают все проверки
- Типы только в изменённых файлах: `pre-commit run mypy --from-ref origin/master --to-ref HEAD`
