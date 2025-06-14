# AGENTS.md

Инструкции для интеграционных тестов.

- Запустите сервисы `docker compose --profile integration up -d`.
- Переменные окружения берутся из `.env`, при необходимости переопределяются в `conftest.py`.
- Не подключайтесь к облачным сервисам и не пропускайте тесты из-за недоступности инфраструктуры.
- Все клиенты Weaviate используют `connect_to_local`.
- Фикстуры `openai_key`, `openai_embedder`, `temp_collection_name`, `clean_alias_collection` объявлены в `conftest.py`.
- Тесты создают временные коллекции в Weaviate и удаляют их после завершения.
