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
- индекс: `docs/README.md`, быстрый старт: `docs/quickstart/agent_quick_start.md`
- `app/main.py` — точка входа

## Код-стайл
- PEP8 + типы, форматирование `black`, линтер `flake8`
- Используйте f-строки
- В `Field()` указывайте `description`
- Логер — `get_logger` из `app.utils.logger`

## Локальный запуск
Подробности в `docs/quickstart/agent_quick_start.md`.

## Тесты
- `pytest -q` (интеграционные тесты только по запросу: `--runintegration`)
- Подробнее — `app/tests/AGENTS.md`
- Каждый тест должен содержать докстринг с описанием проверяемого поведения.

## Pull request
- Краткий глагол в заголовке
- Описание содержит `## Summary` и `## Testing`

## Проверки перед коммитом
- Перед каждым коммитом выполняйте `pre-commit run --all-files`.

### Неиспользуемый код
- `vulture app vulture_whitelist.py` запускается в прекоммите. Если в выводе есть
  функции или переменные, прочитайте отчёт, подтвердите каждую строку и опишите
  результат в PR.

## Баг репорты
- Шаблон: `docs/bugs/bug_report_template.md`
- Имя файла: `mm.dd.n_description.md`, где `n` — порядковый номер в этот день.
- Размещайте баг репорты в каталоге `docs/bugs`.

## Доработки
- Шаблон: `docs/improvements/improvement_template.md`
- Имя файла: `mm.dd.n_description.md`, где `n` — порядковый номер в этот день.
- Доработки размещаются в каталоге `docs/improvements`.
