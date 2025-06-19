# AGENTS.md

Минимальные правила тестирования.

- Дерево тестов повторяет структуру `app/`.
- Unit-тесты (`app/tests/unit`) используют фикстуры из `conftest.py` и не обращаются к внешним сервисам.
- Интеграционные тесты (`app/tests/integration`) требуют `docker compose --profile integration up -d`.
- Запуск: `pytest -q` (добавьте `--runintegration` для интеграции).
- Покрытие: `pytest --cov=app --cov-report=xml:coverage.xml --cov-report=html --cov-fail-under=85 -q`.
- Следуйте TDD и используйте фикстуры, `pytest.mark.parametrize`, один тест — одна проверка.
- У каждого теста должна быть докстринг с кратким описанием проверяемого поведения.
- Инфраструктурные детали описаны в `app/tests/integration/AGENTS.md`.
