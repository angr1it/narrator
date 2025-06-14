# augment_pipeline_status.md
Статус реализации /augment-context

## 🔧 Общий статус
Изначально `/v1/augment-context` был подключён к `_DummyPipeline`,
который сразу выбрасывал `NotImplementedError`.
Теперь эндпоинт использует `AugmentPipeline` из `services.pipeline` —
он ищет подходящие шаблоны, заполняет слоты, выполняет разрешение сущностей и
запускает Cypher‑запросы к графу.

## 📌 Что уже реализовано
1. **Компоненты шаблонов**
   - `TemplateService.top_k` и `top_k_async` фильтруют шаблоны по `supports_augment`.
   - Добавлены шаблоны с суффиксом `_aug_v1.j2`, общие файлы `_augment_filters.j2`, `_augment_meta.j2`.
   - `CypherTemplateBase.render` поддерживает `TemplateRenderMode.AUGMENT`.
2. **Инфраструктурные сервисы**
   - `SlotFiller.fill_slots` извлекает значения слотов с fallback через LLM.
   - `IdentityService.resolve_bulk` учитывает `is_entity_ref` в слотах.
   - `TemplateRenderer.render` возвращает `RenderPlan` с `content_cypher` и `return_keys`.
   - `GraphProxy.run_query` выполняет Cypher-запросы.
   - `ExtractionPipeline` служит примером оркестрации.

## 🧱 Что ещё планируется
- Интеграция summariser для формирования краткой сводки.
- Дополнительные тесты и обработка пограничных случаев.
- Расширенная документация формата ответа.


## 🟢 Степень готовности
Компонент | Готовность
---|---
TemplateService.top_k_async | ✅
SlotFiller | ✅
IdentityService.resolve_bulk | ✅
TemplateRenderer.render | ✅
GraphProxy.run_query | ✅
AugmentPipeline | ✅
FastAPI endpoint | ✅
Summary | ⛔ нет
Тесты | ✅ unit

Пайплайн подключён к API и выполняет основной поток.
Остаётся добавить summariser и покрыть дополнительные случаи тестами.
