Алгоритм работы эндпойнта `` (далее — просто `/extract`) — это основа пайплайна, который превращает сырой литературный текст в граф структурированных связей и связывает их с `ChunkNode` и `RaptorNode`. Ниже — полный, детализированный разбор с акцентом на модели данных и отсутствие фактов как сущностей.

---

## ✅ Общий флоу `/extract`

```mermaid
graph TD
  A[User: chunk, chapter, tags] --> B[/extract-save]
  B --> C[TemplateService]
  C --> D[SlotFiller]
  D --> E[IdentityService]
  E --> F[FlatRaptorIndex]
  F --> G[GraphProxy: create nodes and edges]
  G --> H[Weaviate: alias insert]
```

---

## 📦 Пошагово: что происходит в `/extract-save`

### 1. Входной запрос

```json
{
  "text": "Арен присоединился к Ночному фронту.",
  "chapter": 5,
  "stage": "brainstorm",
  "tags": ["recruitment", "Night Front"]
}
```

→ Преобразуется в модель:

```python
class ExtractSaveIn(BaseModel):
    text: str
    chapter: int
    stage: StageEnum = StageEnum.brainstorm
    tags: list[str] = []
```

Текст ограничен 1000 символами, что примерно соответствует 2–8 предложениям.

---

### 2. Сохраняем ChunkNode (в Neo4j)

```cypher
CREATE (c:Chunk {
  id: $chunk_id,
  text: $text,
  chapter: $chapter,
  tags: $tags,
  draft_stage: $stage,
  raptor_node_id: NULL
})
```

> Это центральная точка привязки. Все связи, ноды и алиасы будут ассоциированы с этим `Chunk.id`.

---

### 3. Template Discovery (semantic search)

🔍 TemplateService ищет Top-K подходящих `CypherTemplate` из Weaviate по embedding текста.

```json
{
  "id": "membership_change",
  "slots": {
    "character": "STRING",
    "faction": "STRING",
    "chapter": "INT"
  },
  "fact_descriptor": {
    "predicate": "MEMBER_OF",
    "subject": "$character",
    "object": "$faction",
    "value": "$faction"
  }
}
```

---

### 4. SlotFiller — извлекаем значения слотов

Запрашиваем LLM (или rules + fallback), чтобы заполнить:

```python
slots = {
  "character": "Арен",
  "faction": "Ночной фронт",
  "chapter": 5
}
```

→ модель данных:

```python
class SlotSchema(BaseModel):
    template_id: str
    slots: Dict[str, str]
    raw_mentions: Dict[str, str]  # "Арен" → CHARACTER, "Ночной фронт" → FACTION
```

---

### 5. IdentityService — получаем entity\_id для всех raw\_name

```python
resolved_slots = {
  "character": "UUID-123",
  "faction": "UUID-456",
}
```

→ Возможны варианты:

- использовать существующий alias
- создать новый \:Character / \:Faction
- добавить синоним

📥 Все алиасы сразу записываются в **Weaviate**:

```json
{
  "alias_text": "Арен",
  "entity_id": "UUID-123",
  "canonical": false,
  "chapter": 5,
  "chunk_id": "chunk-789"
}
```

---

### 6. FlatRaptorIndex — создаем или обновляем `RaptorNode`

- `text_vec` ← embedding текста
- `fact_vec` ← embedding слотов ("Aren MEMBER\_OF Night Front")
- `centroid = α·text + β·fact`

Если похожий `centroid` уже есть (cosine ≥ 0.9) → объединяем с ним\
Иначе → создаем новый `RaptorNode`

> Возвращённый `node_id` сохраняется в `Chunk.raptor_node_id`

---

### 7. Генерация доменных связей (Cypher)

Из шаблона `membership_change` формируются связи, **но не факт**:

```cypher
MERGE (a:Character {id: "UUID-123"})
MERGE (b:Faction {id: "UUID-456"})
MERGE (a)-[:MEMBER_OF {from_chapter: 5}]->(b)
```

Дополнительно:

```cypher
MATCH (c:Chunk {id: $chunk_id})
MERGE (c)-[:MENTIONS]->(a)
MERGE (c)-[:MENTIONS]->(b)
MERGE (c)-[:MENTIONS]->(rel)  // если отношения в графе моделируются нодами
```

---

### 8. GraphProxy — создаёт связи и ноды в Neo4j

- Выполняется единая Cypher-партия (в одной транзакции)
- Никаких `:Fact` не создаётся — связи и объекты идут напрямую от `Chunk`

---

## 🧩 Модели данных: полная схема

### `ChunkNode`

```python
class ChunkNode(BaseModel):
    id: str
    text: str
    chapter: int
    draft_stage: str
    tags: list[str]
    raptor_node_id: str
```

### `AliasRecord` (Weaviate)

```python
class AliasRecord(BaseModel):
    alias_text: str
    entity_id: str
    entity_type: str
    canonical: bool
    chapter: int
    confidence: float
    chunk_id: str
```

### `RaptorNode` (Weaviate)

```python
class RaptorNode(BaseModel):
    node_id: str
    text_vec: np.ndarray
    fact_vec: np.ndarray
    centroid: np.ndarray
    insertions_cnt: int
    chapter_span: Tuple[int, int]
    status: Literal["draft", "stable"]
    summary_text: str | None
```

---

## 🔄 Что возвращается

```json
{
  "chunk_id": "chunk-789",
  "raptor_node_id": "raptor-123",
  "relationships": [
    {"subject": "UUID-123", "predicate": "MEMBER_OF", "object": "UUID-456"}
  ],
  "aliases": [
    {"alias_text": "Арен", "entity_id": "UUID-123"},
    {"alias_text": "Ночной фронт", "entity_id": "UUID-456"}
  ]
}
```

---

## 🧠 Вывод

- `/extract` превращает сырой текст в ChunkNode + граф связей.
- Никаких `:Fact` не создаётся — только доменные связи и ноды.
- Все данные (aliases, embedding, связи) связываются через `chunk_id`
- Готово для последующей агрегации и версиификации через RaptorNode.

