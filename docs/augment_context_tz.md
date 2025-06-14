# 📘 Техническое задание: `/augment-context`

## Доработки

1. **Domain edges lack details.** Relationships like `MEMBER_OF` are created without the `details` produced during slot filling. The `GraphRelationDescriptor.details` field already exists but is ignored. The renderer should pass `SlotFill.details` into the descriptor and templates must write this value to the domain relationship.
2. **Alias decisions lose context.** The prompt `verify_alias_llm.j2` returns a justification string, however `IdentityService` drops it when creating alias tasks. This information should be stored on `AliasRecord` and, when a new entity is created, as a property of that node.
3. **`chunk_mentions.j2` conflates chunk linkage and domain data.** This template currently adds `triple_text` and `details` onto `MENTIONS` edges. It will be renamed to `chunk_mentions.j2` and keep only the `MATCH`/`MERGE` logic linking entities with the originating chunk.
4. **Shared descriptor snippet.** Domain templates repeat boilerplate to add `template_id`, `chapter` and future `details` to relationships. A small Jinja partial can expose fields from `GraphRelationDescriptor` so that domain templates simply include it.

Эти изменения позволяют извлекать обоснование из графа и делают пайплайн аудируемым.

## Реализованные изменения

### TemplateService
- Loads built‑in templates at startup using `ensure_base_templates`.
- Weaviate schema now includes `augment_cypher`, `use_base_augment` and `supports_augment`.
- `top_k` and `top_k_async` accept `TemplateRenderMode` to filter augmentation templates.

### CypherTemplate
- `render` принимает `TemplateRenderMode` и валидирует поля для augment.
- Обёртка `chunk_mentions.j2` может быть отключена через `use_base_extract` или `use_base_augment`.

### IdentityService
- `resolve_bulk` теперь получает определения слотов и пропускает те, где `is_entity_ref=False`.

### Templates
- Добавлены файлы запросов c суффиксом `_aug_v1.j2`.
- Общие частичные `_augment_filters.j2` и `_augment_meta.j2` сокращают повторения.

### Tests
- Unit tests покрывают рендеринг augment, импорт шаблонов и фильтрацию top‑k.

## Итоговое состояние

`AugmentPipeline` реализован и подключён к `/v1/augment-context`. Он ищет подходящие шаблоны, заполняет слоты, разрешает идентичности и выполняет Cypher-запросы через `GraphProxy`. Возвращаются строки результата, опциональная краткая сводка будет добавлена позднее.

Предстоящие задачи:
1. Интегрировать summariser для сжатия результатов.
2. Расширить юнит- и интеграционные тесты.
3. Завершить документацию формата запроса и правила тегов шаблонов.
