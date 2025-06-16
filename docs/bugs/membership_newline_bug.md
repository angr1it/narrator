# Membership augment newline bug

## Проблема
При вызове `/augment-context` для шаблона `membership_change_aug_v1.j2` падает `CypherSyntaxError`.
Логи содержат фрагмент запроса `WHERE true AND r.chapter <= 1WITH r, f`.

## Контекст
Файл `membership_change_aug_v1.j2` подключает `_augment_filters.j2` перед оператором `WITH`:

```
{% include "_augment_filters.j2" %}
WITH r, f
```

Jinja2 настроен с `trim_blocks=True`, поэтому пустая строка между блоком и `WITH` удаляется.
Получается строка без пробела и Neo4j не может распознать `WITH`.

## Причина
Блок `_augment_filters.j2` заканчивается конструкцией `{% endif %}`.
Из-за `trim_blocks` завершающий перевод строки опускается и текст `WITH r, f` склеивается с предыдущим.

## Последствия
Эндпоинт `/augment-context` возвращает 500.
Запросы к графу не выполняются.

## Планируемые изменения
Добавить пустую строку после включения `_augment_filters.j2`.
Это сохранит перевод строки даже при `trim_blocks`.

## Локация
- `app/templates/cypher/membership_change_aug_v1.j2`

## Улучшения
Рассмотреть переход на подзапросы `CALL {}` чтобы не разделять шаблоны вручную.

## Деплой
Пересобрать контейнер, миграций не требуется.

## Проверка
- `pytest -q`
- Ручной вызов `/augment-context` для текста и главы 1 должен вернуть ответ без ошибки.

## Отчёт
После исправления запрос рендерится как:

```
MATCH (c:Character {id: "x"})-[r:MEMBER_OF]->(f:Faction)
WHERE true AND r.chapter <= 1
WITH r, f
```

Neo4j принимает такой синтаксис без ошибок.

## Дополнительная проверка
Просмотрены все шаблоны в `app/templates/cypher`. После `_augment_filters.j2` только `membership_change_aug_v1.j2` содержит Cypher-оператор (`WITH`).
В остальных файлах после включения следуют лишь Jinja-переменные, поэтому проблема не проявляется.
Похожий баг ранее исправлялся для `chunk_mentions.j2` (commit `6cf0385`).

## Тесты
Добавлен юнит-тест `test_membership_filters_newline`, который рендерит шаблон и проверяет, что `WITH r, f` начинается с новой строки.

