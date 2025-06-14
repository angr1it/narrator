# AGENTS.md

Общие правила работы с репозиторием. Вложенные файлы могут дополнять эти инструкции.

## Структура
- `app/api` — FastAPI маршруты
- `app/services` — бизнес-логика
- `app/schemas` — Pydantic модели
- `app/config` — клиенты внешних сервисов
- `app/core` — общая инфраструктура
- `app/utils` — логирование и helpers
- `app/templates` — Jinja2-шаблоны
- `app/tests` — тесты
- `docs/` — документация
- `app/main.py` — точка входа

## Код-стайл
- PEP8 + типы, форматирование `black`, линтер `flake8`
- Используйте f-строки
- В `Field()` указывайте `description`
- Логер — `get_logger` из `app.utils.logger`

## Локальный запуск
1. Создайте `.env` по примеру
2. `docker compose up -d`
3. Для интеграционных тестов: `docker compose --profile integration up -d`
4. Проверьте Weaviate: `curl http://localhost:8080/v1/meta`

## Тесты
- `pytest -q` (интеграция: `--runintegration`)
- Покрытие: `pytest --cov=app --cov-report=xml:coverage.xml --cov-report=html --cov-fail-under=85 -q`
- Подробнее — `app/tests/AGENTS.md`

## Pull request
- Краткий глагол в заголовке
- Описание содержит `## Summary` и `## Testing`

## Обязательные проверки
- `black --check .`
- `flake8`
- `mypy .`
- `pytest --cov=app --cov-report=xml:coverage.xml --cov-report=html --cov-fail-under=85 -q`

### Pre-commit
- Выполните `pre-commit install`
- Хуки запустят проверки
- Проверка типов для изменённых файлов: `pre-commit run mypy --from-ref origin/master --to-ref HEAD`
