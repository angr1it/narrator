# 🧠 RAPTOR Extraction Pipeline — Архитектура и Взаимодействие Компонентов

## 🗂 Общий Обзор

Цель пайплайна — извлекать **структурированные утверждения** (факты) из нарратива и проецировать их в **граф знаний** (Neo4j) + **семантический индекс** (Weaviate).  
Архитектура поддерживает versioning, aliasing, filtering по главам и стадиям (`StageEnum`), traceability и контроль достоверности (`confidence`, `canonical`).

---

## 🔄 Компоненты и Поток Выполнения

### 1. `TemplateService`
- Ищет top-K шаблонов (`CypherTemplate`) по вектору текста.
- Передаёт шаблоны дальше в `SlotFiller`.

---

### 2. `SlotFiller`
- Прогоняет 3 фазы (`extract`, `fallback`, `generate`) через LLM.
- Возвращает список `SlotFill`:
  ```json
  {
    "template_id": "...",
    "slots": {"character": "Арен", "trait": "храбрый"},
    "details": "via extraction"
  }
  ```

---

### 3. `IdentityService.process_slot_fills()`
- Находит ближайшие `alias`-ы в Weaviate.
- При необходимости создаёт:
  - новые `entity_id`;
  - Cypher-запросы на вставку в Neo4j;
  - записи `Alias` в Weaviate.
- Выдаёт:
  - обновлённые `SlotFill` (все имена → `entity_id`);
  - `alias_cypher[]` (вставить перед основным контентом).

---

### 4. `TemplateRenderer`
- Рендерит **контентный Cypher** из `CypherTemplate` и `SlotFill`.
- Также возвращает `return_map` (соответствие ключей ↔ UID в графе).

---

### 5. `GraphProxy`
- Выполняет сначала `alias_cypher`, затем `content_cypher`.
- Возвращает UID-ы сущностей.

---

### 6. `FactBuilder`
- На основе шаблона + `return_map` строит **versioned факт**:
  - проверяет `MERGE` с предыдущими,
  - `SET active = false`,
  - создаёт новый `(:Fact)` с `stage`, `tags`, `from_chapter`, `to_chapter`.

---

### 7. `GraphProxy` (второй вызов)
- Выполняет `fact_cypher`.

---

## 🧩 Объекты и связи

- `(:Alias)` — всегда связан с `(:Character|Location|Faction)` через `:REFERS_TO`
- `(:Fact)` — связан с `(:Alias)` и основными сущностями
- `(:Fact)` может иметь `PRECEDED_BY` к старым версиям
- `canonical` и `confidence` управляют зрелостью alias

---

## ✅ Пример последовательности

1. Ввод: `"Арен сражался смело"`
2. Найден шаблон `character_trait`
3. Извлечено:
   ```json
   { "character": "Арен", "trait": "храбрый" }
   ```
4. `IdentityService`:
   - создаёт `character-xxx`
   - добавляет `Alias`
   - генерирует Cypher
5. Выполняется `alias_cypher`
6. Рендерится `content_cypher`: `(:Character)-[:HAS_TRAIT]->(:Trait)`
7. Выполняется `content_cypher`
8. `FactBuilder` создаёт `versioned_fact`
9. Записывается `(:Fact)`

---

## 🛠 Контрольные поля

- `stage`: `StageEnum` (-1 → brainstorm, 0 → outline, ..., 11 → final)
- `chapter`, `to_chapter`: для хронологии
- `tags`: дополнительные метки
- `details`: trace цепочки рассуждений

---

## 📌 Поддержка

- 🔁 Idempotency через `MERGE`
- 🧠 LLM используется **только** при неуверенных alias
- 🔐 Все `entity_id` канонизированы
- 📒 Обратная трассировка: `fact -> slot_fill -> template -> text`

---