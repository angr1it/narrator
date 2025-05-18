# StoryGraph Service – Technical and Architectural Overview

This document serves as a live specification for the StoryGraph prototype. It includes a detailed breakdown of the service's functional purpose, architectural components, data flow, implementation classes, and key algorithms.

---

## 1. Purpose and Functionality

StoryGraph is a backend service that supports intelligent story authoring by extracting and querying narrative facts (characters, events, traits, locations, etc.) from free-form text. It leverages an explicit graph model (Neo4j) and a structured template-driven approach to ensure consistent and traceable updates to the story world.

Two primary operations:

### A. `extract-save` → (text → graph)
- Input: passage (2–8 sentences) + metadata (chapter, tags)
- Output: Cypher `CREATE` / `MERGE` queries for Neo4j
- Logic: Detect narrative structure using templates, fill required slots using LLM, generate Cypher and insert data into Neo4j.

### B. `augment-context` → (text → contextual data)
- Input: passage + metadata (chapter, tags)
- Output: Contextual facts from the graph relevant to continuing writing (traits, relationships, arcs, etc.)
- Logic: Analyze the passage, derive internal queries, retrieve from Neo4j via `Cypher SELECT`, and return a trimmed structured context.

---

## 2. Architecture

```mermaid
graph TD
CLIENT --> API
API --> PIPELINE[Pipeline Layer]
PIPELINE --> TEMPLATE_SVC[TemplateService (Weaviate)]
PIPELINE --> GRAPH_PROXY[GraphProxy (Neo4j)]
PIPELINE --> LLM_FILLER[LLM Slot Filling]
PIPELINE --> LOGGER[Mongo or stdout]
```

### Stack:
- FastAPI (Python 3.11+)
- LangChain + OpenAI API
- Weaviate (for template vector search)
- Neo4j (Cypher-based graph model)
- Optional: MongoDB (misses, logs)
- Langfuse (LLM tracing)

---

## 3. Algorithm: Extract & Save Facts

### Step-by-step:
1. **Input**: Chunk of 2–8 sentences + metadata:
   - `chapter` number
   - `tags` (optional, user-defined)
2. **Template Discovery**: 
   - Use Weaviate to find top-K most semantically relevant Cypher templates for the input chunk.
3. **Slot-Focused LLM Extraction**:
   - For each selected template:
     - Read its `slot_schema`
     - Ask LLM to extract values **only for these named slots** from the text
4. **Slot Completion**:
   - If required slots are still missing: issue fallback LLM prompt.
   - For free-text fields (e.g. summary, event_name): issue separate generation prompt.
5. **Fact Scope Classification**:
   - Ask LLM if the extracted fact is **chapter-specific** or **global/timeless**.
   - If chapter-specific → add `IN_CHAPTER` relationship
   - If global → add a `Fact` node without binding to a chapter, or with version markers
6. **Render Cypher**: Fill slots into Jinja2 Cypher template.
7. **Enrich & Save**:
   - Attach optional tags to the fact or fragment
   - Run batch of Cypher `CREATE` / `MERGE` statements via GraphProxy
8. **Log and trace**: Send all LLM calls to Langfuse for traceability.

---


## 4. Versioning of Facts (Temporal Conflict Resolution)

To support the dynamic and evolving nature of narratives, **versioning** is implemented for all types of changeable facts. This avoids overwriting or deleting historical information and enables consistent time-aware querying.

### 1. Principles of Versioning

- Facts are stored in dedicated `:Fact` nodes rather than directly mutating entity properties.
- Each `Fact` node may include:
  - `from_chapter` — the chapter when the fact became true
  - `to_chapter` — the chapter when the fact ceased to be valid (or `NULL` if still active)
  - `PRECEDED_BY` links to the prior version, enabling full temporal lineage

### 2. What Should Be Versioned

| Entity        | Versioned via Fact? | Notes                                                            |
|---------------|---------------------|------------------------------------------------------------------|
| Character     | ✅                  | Dynamic fields (status, titles, affiliations) via `Fact`         |
| Item          | ⚠️                  | Physical identity stable; traits and ownership as `Fact`         |
| Location      | ⚠️                  | Geography stable; usage or ownership via `Fact`                  |
| Trait         | ⚠️                  | If innate → not versioned; otherwise via `HAS_TRAIT` `Fact`      |
| Faction       | ⚠️                  | Member lists via `Fact`, not internal structure                  |
| Event         | ❌                  | Events are timestamped points; no need for versioning            |
| Fact          | ✅                  | Core unit of versioning                                          |

---

### 3. Implementation: Two-Phase Template Strategy (Recommended)

To decouple domain-specific data creation from version tracking, we separate template execution into two distinct steps:

#### **Phase 1: Execute Content Template**
- Fill and execute a `CypherTemplate` that describes the basic event or structure (e.g. a character gains an item).
- No versioning logic embedded here.

#### **Phase 2: Conditionally Add Versioned Fact**
- Prompt the LLM with a post-question:
  > _“Should the fact implied by this text be versioned?”_
- If yes → fill a generic `versioned_fact.j2` with required slots:
  - `subject_id`, `object_id` (optional), `type`, `value`, `chapter`, `summary`
- Execute the second Cypher block independently.

#### Template Class Extension
```python
class CypherTemplate(BaseModel):
    id: str
    category: str
    title: str
    description: str
    cypher: str
    slot_schema: Dict[str, str]
    fact_policy: Literal["none", "auto", "always"] = "auto"
    fact_type: str | None = None
    fact_value_slot: str | None = None
```

---

### 4. Universal Fact Template (`versioned_fact.j2`)

```jinja2
MERGE (subj {id: '{{ subject_id }}'})
{% if object_id %}MERGE (obj {id: '{{ object_id }}'}){% endif %}
WITH subj{% if object_id %}, obj{% endif %}
OPTIONAL MATCH (prev:Fact)
  WHERE prev.subject_id = '{{ subject_id }}'
    {% if object_id %}AND prev.object_id = '{{ object_id }}'{% endif %}
    AND prev.type = '{{ type }}'
    AND (prev.to_chapter IS NULL OR prev.to_chapter >= {{ chapter }})

FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
  SET prev.to_chapter = {{ chapter }} - 1
)

CREATE (f:Fact {
  id: randomUUID(),
  type: '{{ type }}',
  subject_id: '{{ subject_id }}',
  {% if object_id %}object_id: '{{ object_id }}',{% endif %}
  value: '{{ value }}',
  from_chapter: {{ chapter }},
  to_chapter: NULL,
  summary: '{{ summary }}'
})
MERGE (subj)-[:ASSERTED]->(f)
{% if object_id %}MERGE (f)-[:REFERS_TO]->(obj){% endif %}
FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
  CREATE (f)-[:PRECEDED_BY]->(prev)
)
```

---

### 5. Querying the Active Fact at a Chapter

```cypher
MATCH (f:Fact)
WHERE f.subject_id = 'Eric'
  AND f.type = 'STATUS'
  AND f.from_chapter <= $current
  AND (f.to_chapter IS NULL OR f.to_chapter >= $current)
RETURN f
ORDER BY f.from_chapter DESC
LIMIT 1
```

This allows precise fact filtering to construct coherent story state for any given moment.

---


### 6. Example Pipeline Flow

```text
Input:
  Text = "К 10‑й главе Эрик возненавидел Volvo"
  Chapter = 10

Phase 1:
  Template = event_emotion_change
  → Cypher = CREATE node Eric, Volvo, emotion='hate'

Phase 2:
  LLM says: "yes, version it"
  → versioned_fact.j2:
     type = "EMOTION"
     subject = "Eric"
     object = "Volvo"
     value = "hate"
     chapter = 10

Final Cypher:
  Content Cypher + Versioned Fact Cypher (batched)
```

---

### 7. Benefits of Two-Phase Strategy

- Keeps domain templates clean and reusable
- Provides centralized control over version logic
- Allows LLM to make contextual judgments per use case
- Easier to test and debug versioning rules independently
- **Temporal fidelity** — track evolving storylines without data loss
- **Non-destructive updates** — future contradictions don't erase history
- **Query flexibility** — full state reconstruction for any chapter or interval


## 5. Core Classes

### `CypherTemplate`
Handles a single template with:
- `cypher`: raw Jinja2 Cypher code (can include versioning logic)
- `slot_schema`: expected named variables with types
```python
class CypherTemplate(BaseModel):
    id: str
    category: str
    title: str
    description: str
    cypher: str
    slot_schema: Dict[str, str]
    def render(self, slots: Dict[str, Any]) -> str: ...
```

### `TemplateService`
Interface to Weaviate vector DB. Provides semantic template retrieval.

### `GraphProxy`
Wraps Neo4j Cypher execution.

### `SlotFiller`
Encapsulates logic to fill slots using LLM.

### `ExtractionPipeline`
Runs the extract-and-save process.

### `AugmentPipeline`
Handles augment-context logic.

---

## 6. Slot Filling Logic (LLM-first)

```python
def fill_slots_for_template(template, chunk, meta):
    slots = {"chapter": meta["chapter"], "source_text": chunk}

    # 1. Determine required named slots
    named_slots = [k for k, typ in template.slot_schema.items()
                   if not typ.lower().endswith("(optional)")
                   and not k.startswith("event_") and k != "summary"]

    # 2. Extract via LLM
    extracted = llm_extract_specific_slots(chunk, required=named_slots)
    slots.update(extracted)

    # 3. Fallback for required but missing
    missing = [k for k in named_slots if k not in slots]
    if missing:
        slots.update(llm_fallback(chunk, missing))

    # 4. Generate summary and other descriptive fields
    generative = [k for k in template.slot_schema if k not in slots]
    if generative:
        slots.update(llm_generate(chunk, context=slots, fields=generative))

    return slots
```

---

## 7. Template Example
```json
{
  "id": "event_revelation_character_trait",
  "title": "trait revelation",
  "description": "When one character reveals a hidden trait of another",
  "examples": ["Мира раскрыла, что Арен родился с дефектом руки"],
  "cypher": "...",
  "slot_schema": {"actor": "STRING", "trait": "STRING"},
  "vector": [0.123, 0.456, ...]
}
```

---

## 8. Summary: What Is Implemented Now
- FastAPI service with `/v1/extract-save` and `/v1/augment-context`
- Jinja2-based Cypher templates with LLM-filled slot schema
- LLM-only extraction pipeline (NER + fallback + freeform)
- In-memory or mock `TemplateService`, ready for Weaviate integration
- `GraphProxy` abstraction for Cypher query execution
- Versioned fact insertions (with `PRECEDED_BY` and chapter intervals)

---

## 9. Next Steps
- Implement LangChain prompt wrappers (extract, fallback, generate)
- Add Langfuse `trace_id` to all LLM steps
- Finish Weaviate-based template search
- Replace mock graph proxy with Neo4j driver
- Include `TextFragment` and `IN_CHAPTER` in Cypher patterns
- Add automated test harness for both pipelines
- Introduce support for `from_chapter`, `to_chapter` versioning in graph model

---
