На основе текущей архитектуры (`ChunkNode → доменные связи → RaptorNode`) и уже проведённого рефакторинга моделей, ниже — краткий обзор **изменений в моделях** и **подробное описание их применения для построения графа**:

---

## ✅ Изменения в моделях (сводка)

### 1. `SlotDefinition`

**Без изменений.**\
Отвечает только за описание типов данных для LLM-экстракции. Возможные будущие расширения:

- `is_entity_ref: bool` — явное указание, что слот требует identity-resolution.
- `enum_values: list[str]` — если набор возможных значений ограничен.

---

### 2. `FactDescriptor` → `GraphRelationDescriptor`

**Реализация:**

```python
class GraphRelationDescriptor(BaseModel):
    predicate: str                  # MEMBER_OF, OWNS, etc.
    subject: str                    # "$character"
    object: Optional[str] = None    # "$faction"
    value: Optional[str] = None     # текстовая реплика или количественное значение
```

**Роль:**

- семантический контракт для интерпретации рендеренных связей;
- источник `subject`/`object` для связи с `ChunkNode`;
- позволяет из слотов сгенерировать `triple_text` → `fact_vec`.

---

### 3. `CypherTemplateBase`

**Добавлены поля:**

```python
attachment_policy: Literal["chunk", "raptor", "both"] = "chunk"
default_confidence: float = 0.2
graph_relation: Optional[GraphRelationDescriptor]
```

**Пояснение:**

- `attachment_policy` управляет, где следует фиксировать ссылку (`MENTIONS`, `REFERS_TO`).
- `default_confidence` убирает захардкоженное значение из пайплайна.
- `graph_relation` помогает с генерацией `fact_vec`.

---

### 4. `RenderedCypher`

**Возможное переименование:**

```python
fact_cypher → relation_cypher
```

**Обоснование:** термина `факт` как сущности в графе больше нет.

---

## 🔗 Как используются модели при формировании графа

### 📌 Передаваемые параметры и их роли

| Параметр           | Где используется                                  | Назначение                                                                                  |
| ------------------ | ------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `chunk_id`         | `chunk_mentions.j2`, Cypher шаблон, aliases, embedding | Связывает все действия (ноды, связи, алиасы, raptor) с одним чанк-блоком текста.            |
| `related_node_ids` | `chunk_mentions.j2`                                    | Список ID сущностей, участвующих в доменных отношениях; позволяет связать их с `ChunkNode`. |
| `template_id`      | Cypher → `MERGE (... {template_id: ...})`         | Логирует происхождение связи — из какого шаблона она произошла.                             |
| `description`      | Cypher, UI                                        | Текстовая подпись/расшифровка, вставляемая в свойства рёбер и узлов.                        |
| `confidence`       | Cypher                                            | Уровень уверенности (например, для weak facts из LLM).                                      |
| `draft_stage`      | Cypher, Chunk                                     | Используется для версионирования и фильтрации по прогрессу работы над сценой.               |
| `triple_text`      | → `fact_vec`                                      | Формирует семантическое представление факта в векторном виде.                               |

---

### Шаг 1: `CypherTemplateBase.render(slots, chunk_id)`

Метод `render()` принимает не только `slots`, но и дополнительно передаёт в шаблон `chunk_id` — чтобы шаблон мог включить ссылку на `ChunkNode` в финальный Cypher.

#### Пример:

```python
rendered = template.render(
    slots={"character": "UUID-1", "faction": "UUID-2"},
    chunk_id="chunk-xyz"
)
```

Внутри `render()`:

```python
context["chunk_id"] = chunk_id  # передаётся явно
```

Шаблон `chunk_mentions.j2` затем использует это значение для вставки:

```cypher
MATCH (chunk:Chunk {id: "{{ chunk_id }}"})
```

Таким образом, `chunk_id` — **внешний параметр**, передаваемый из Extraction-пайплайна при запуске шаблона.

#### Итого, `chunk_id`:

- задаётся один раз при вызове `/extract` и присваивается `ChunkNode`;
- передаётся в `template.render()` и попадает в Jinja-контекст;
- используется внутри шаблона для `MATCH`, `MERGE`, `chunk_id`-атрибутов в отношениях.

1. **Подставляет значения в шаблон.**
2. **Формирует**:
   - `content_cypher` — команды `MERGE` для доменных связей (Character → Faction).
   - `triple_text` — семантическая строка `"Aren MEMBER_OF Night Front"`.
3. **Извлекает** `related_node_ids` из `GraphRelationDescriptor`.

---

### Шаг 2: `chunk_mentions.j2` добавляет обвязку

```jinja2
WITH *
MATCH (chunk:Chunk {id: "{{ chunk_id }}"})
{% for node_id in related_node_ids %}
  MATCH (x{{ loop.index }} {id: "{{ node_id }}"})
{% endfor %}
{% for node_id in related_node_ids %}
  MERGE (chunk)-[:MENTIONS]->(x{{ loop.index }})
{% endfor %}
```

`MATCH`-часть выполняется перед `MERGE`. Пайплайн разделяет запрос по ``WITH *``
и исполняет его двумя последовательными командами, избегая ошибки Neo4j.

Это формирует привязку всех связанных сущностей к `ChunkNode`.

---

### Шаг 3: SlotFiller → triple\_text → `fact_vec`

```python
triple_text = f"{subject} {predicate} {object}"
fact_vec = encoder.encode([triple_text])[0]
```

→ используется в:

```python
centroid = α * text_vec + β * fact_vec
```

и сохраняется в `RaptorNode`.

---

### Шаг 4: GraphProxy

- Выполняет рендеренный `content_cypher` (и, опц., `alias_cypher`).
- Фиксирует `:Chunk`, `:Character`, `:Faction`, `:Location` и т.д., а также связи между ними.
- Обеспечивает транзакционную атомарность.

---

### Шаг 5: Связь с `RaptorNode`

- После рендера все связи содержат `chunk_id`.
- `ChunkNode` содержит `raptor_node_id`.
- Таким образом можно проследить: доменная связь ← `Chunk` ← `RaptorNode`.

---

## 🧠 Вывод

1. `GraphRelationDescriptor` — ключевой семантический слой: связывает шаблон, фактическую тройку и структурный рендер.
2. `CypherTemplateBase` остаётся универсальным контрактом для генерации Cypher, в том числе — в связке с `ChunkNode` и `RaptorNode`.
3. `RaptorNode` использует `fact_vec` наравне с `text_vec`, обеспечивая смысловую кластеризацию.
4. Связь всех сущностей идёт через `chunk_id`, что гарантирует трассируемость, версионирование и возможность удаления/редактирования по одному источнику.

Если хочешь, могу дополнительно:

- сгенерировать JSON-схему для новых моделей;
- предложить миграционные скрипты шаблонов;
- показать тест-кейс полного флоу с примерами моделей и Cypher.
