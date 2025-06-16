# Codex Dev Environment

Этот документ описывает настройку локальной среды для запуска Codex-агента и интеграционных тестов.

## Требования

- macOS с установленным Docker Desktop
- Node.js v22+ и npm
- Python 3.11+
- Установленный [Codex CLI](https://github.com/openai/openai-codex)

## Установка Codex CLI
```bash
npm install -g @openai/codex
export OPENAI_API_KEY="sk-..."
```


## Запуск
1. Поднимите инфраструктуру и запустите интеграционные тесты:
   ```bash
   make integration-test
   ```
2. Запустите Codex для исправления тестов:
   ```bash
   codex --approval-mode full-auto
   ```

Агент автоматически запустит `make integration-test`, проанализирует ошибки и предложит правки.