Отличная идея — выносить базовые графовые связи в универсальный `base.j2`-шаблон, а **доменные шаблоны** (`membership_change`, `status_update`, и т.д.) делать расширениями, которые определяют только семантические части (`MERGE`, `MATCH`, и пр.). Это позволит:

- централизованно реализовать связи с `ChunkNode` и их traceability,
- создать единую точку вставки метаинформации (`template_id`, `chapter`, `chunk_id`, `description`, `draft_stage`, `confidence`),
- обеспечить согласованное поведение для всех шаблонов — единый «контейнер-связь».

---

## ✅ Структура шаблонов

### 1. Что такое шаблон (CypherTemplate)

Шаблон — это Jinja2-описание одного доменного паттерна (например, присоединение к фракции, передача предмета и т.д.), которое генерирует Cypher-код.

### 🧩 Откуда берётся `related_node_ids`

Поле `related_node_ids` — это список ID сущностей, которые должны быть логически и графово связаны с `ChunkNode`. Оно формируется в `render()`:

- если в шаблоне задан `graph_relation`, система извлекает `subject` и `object`, подставляет соответствующие значения из `slots` и добавляет их в `related_node_ids`;
- это позволяет автоматически подключить нужные MATCH- и MENTIONS-блоки в `chunk_mentions.j2`, даже если автор шаблона их не прописал явно;
- это значение также может быть переопределено вручную в Jinja (`{% set related_node_ids = [...] %}`), что даёт гибкость при необходимости.

---

### 2. `chunk_mentions.j2` — базовая рамка шаблона

```
// chunk_mentions.j2

{% include "templates/{{ template_id }}.j2" %}

WITH *
// --- связи с Chunk ---
MATCH (chunk:Chunk {id: "{{ chunk_id }}"})

{% for node_id in related_node_ids %}
  MATCH (x{{ loop.index }} {id: "{{ node_id }}"})
{% endfor %}
{% for node_id in related_node_ids %}
  MERGE (chunk)-[:MENTIONS]->(x{{ loop.index }})
{% endfor %}
```

Здесь `MATCH`‑блок выполняется раньше `MERGE`. Пайплайн разбивает
сгенерированный запрос на две части по ключевому слову ``WITH *`` и выполняет
их последовательно в одной транзакции. Это обход ограничений Neo4j на
комбинацию `MERGE` и `MATCH` в одном запросе.

### 🔍 Что делает цикл `for node_id in related_node_ids`

Этот блок отвечает за то, чтобы:

1. **Связать все сущности, упомянутые в шаблоне, с \`\`.** Это создаёт `MENTIONS`-связи между чанком и каждой задействованной сущностью (персонажем, фракцией и т.п.).
2. **Обеспечить доступность всех сущностей в MATCH-блоках, чтобы использовать их как привязанные переменные.**
3. **Абстрагироваться от конкретных типов нод.** Используемая переменная `x{{ loop.index }}` — это обобщённая нода, которую можно использовать без знания её типа (`:Character`, `:Faction`, и т.д.).
4. **Формирует связность графа.** Позволяет по `ChunkNode` находить все сущности, которые в нём были задействованы.

---

### 3. Доменный шаблон: `membership_change.j2`

```
// templates/membership_change.j2

MERGE (a:Character {id: "{{ character }}"})
MERGE (b:Faction {id: "{{ faction }}"})
MERGE (a)-[r:MEMBER_OF {
    chapter: {{ chapter }},
    template_id: "membership_change",
    description: "{{ description }}",
    chunk_id: "{{ chunk_id }}",
    draft_stage: "{{ draft_stage }}",
    confidence: {{ confidence }}
}]->(b)

{% set related_node_ids = [character, faction] %}
```

---

## 📌 Итог: как это работает

1. `TemplateService` выбирает шаблон `membership_change` по ID.
2. Перед рендерингом `jinja`, система подготавливает:
   ```
   template_context = {
       "template_id": "membership_change",
       "chunk_id": "chunk-abc",
       "chapter": 5,
       "description": "Арен присоединился к Ночному фронту.",
       "draft_stage": "brainstorm",
       "confidence": 0.2,
       "character": "UUID-1",
       "faction": "UUID-2",
       "related_node_ids": ["UUID-1", "UUID-2"]
   }
   ```
3. Рендерится сначала `membership_change.j2`, затем он **включается** в `chunk_mentions.j2`.

---

### Остальная структура шаблонов

(см. предыдущие разделы — примеры шаблонов `membership_change.j2`, объяснение `{% for node_id in related_node_ids %}` и т.д.)

---

## 🔧 Расширение base\_fact.j2 в config-layer

-Чтобы `chunk_mentions.j2` было универсально и подключалось по флагу, подключение управляется через поля `use_base_extract` и `use_base_augment` в `CypherTemplateBase`.
-При рендеринге (в `render()` или TemplateService) `chunk_mentions.j2` задаётся как основной шаблон, а доменный шаблон — как внутренний блок `include`.
- это даст возможность отключить `chunk_mentions` для специальных (alias/identity) шаблонов.



\---

## ✅ Проверка согласованности моделей и структуры шаблонов

Модели `CypherTemplate`, `SlotDefinition`, `GraphRelationDescriptor` хорошо согласуются с идеей вынесения общей логики (`MATCH Chunk`, `MENTIONS`, `traceability`) в `chunk_mentions.j2`:

- ✅ поля `extract_cypher` и `augment_cypher` задают Jinja‑шаблоны для разных режимов; `use_base_extract` и `use_base_augment` управляют обёрткой `chunk_mentions.j2`.
- ✅ `graph_relation` используется для семантической агрегации (triple\_text) и может влиять на `fact_vec` и `related_node_ids`.
- ✅ `render()` теперь добавляет `related_node_ids` из `graph_relation` если они не заданы явно.
- ✅ `RenderedCypher` разделяет `content_cypher`, `fact_cypher`, `alias_cypher`, что позволяет работать с составными шаблонами.

🔧 Возможные доработки:

- `TemplateService` может управлять логикой включения `chunk_mentions.j2` централизованно, а не внутри каждого шаблона.
- Расширить `fact_policy`, чтобы он влиял не только на postprocessing, но и на выбор шаблона рендеринга.
