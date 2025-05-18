# CypherTemplate Specification (v2)

## 🎯 Purpose

`CypherTemplate` defines how to transform narrative text into Cypher code and, optionally, a versioned `Fact`.  
It includes:

- `slots`: variable inputs extracted from text
- `cypher`: name of the Jinja2 template file
- `fact_descriptor`: optional metadata for generating a `Fact`
- `vector`: semantic embedding used for retrieval

---

## 📦 Model Structure

```python
class CypherTemplate(BaseModel):
    id: str
    version: str = "1.0.0"
    title: str
    description: str
    details: Optional[str] = None
    category: Optional[str] = None

    slots: List[SlotDefinition]
    cypher: str
    fact_descriptor: Optional[FactDescriptor] = None

    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    vector: Optional[List[float]] = None
```

---

## 🔧 Vector Embedding

```text
vector := embedding(title + " " + description + " " + (details or ""))
```

Used in:
- `TemplateService.top_k(query)`
- `upsert()` when saving to Weaviate

---

## 🧩 Components

### `SlotDefinition`

```python
class SlotDefinition(BaseModel):
    name: str
    type: Literal["STRING", "INT", "FLOAT", "BOOL"]
    description: Optional[str]
    required: bool = True
    default: Optional[Union[str, int, float, bool]]
```

### `FactDescriptor`

```python
class FactDescriptor(BaseModel):
    predicate: str
    subject: str
    value: str
    object: Optional[str] = None
```

- Uses slot-style placeholders like `$character`, `$trait`
- Resolved at render-time by `CypherTemplate.render(slots)`

---

## ⚙️ Rendering Logic

`.render(slots: dict)`:

- Validates required slots
- Prepares Jinja2 environment and loads `cypher` file
- Adds computed `fact` into context (if descriptor is set)
- Renders and returns Cypher code string

```python
env = Environment(loader=FileSystemLoader("templates/cypher"))
template = env.get_template(self.cypher)
return template.render(**context)
```

---

## 📌 Example Template (JSON)

```json
{
  "id": "trait_attribution_v1",
  "title": "Trait attribution",
  "description": "Character gains or shows a trait.",
  "details": "A hero may be brave in danger, a villain cruel after defeat. This reveals character depth.",
  "category": "EventInsert",
  "slots": [
    { "name": "character", "type": "STRING", "description": "Character name" },
    { "name": "trait", "type": "STRING", "description": "Trait name" },
    { "name": "chapter", "type": "INT" },
    { "name": "summary", "type": "STRING", "required": false }
  ],
  "cypher": "trait_attribution.j2",
  "fact_descriptor": {
    "predicate": "HAS_TRAIT",
    "subject": "$character",
    "value": "$trait",
    "object": "$trait"
  }
}
```

---

## 📂 Sample Template File: `trait_attribution.j2`

```jinja2
MERGE (c:Character {name:'{{ character }}'})
MERGE (t:Trait {name:'{{ trait }}'})
MERGE (c)-[:HAS_TRAIT]->(t)

{% include 'universal_fact.j2' %}
```

---

## 🧠 Usage Scenarios

- `extract-save` uses this template with LLM-filled `slots`
- If `fact_descriptor` is defined, inserts `Fact` node
- Versioning is applied separately (not inside the template)
