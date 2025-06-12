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

## 3. Extract & Save Pipeline

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
5. **Render Cypher**: Fill slots into Jinja2 Cypher template.
6. **Commit & Cluster**:
    - Execute alias Cypher and template Cypher via GraphProxy.
    - After success compute `text_vec` and `fact_vec` and call
      `flat_raptor.insert_chunk()` to set `ChunkNode.raptor_node_id`.
7. **Log and trace**: Send all LLM calls to Langfuse for traceability.


## 4. Versioning via `RaptorNode`

The service maintains history without a dedicated `Fact` node. Each `ChunkNode` stores a `raptor_node_id` pointing to a cluster of semantically similar fragments. Since all created relations include `chunk_id`, the story state for any chapter can be reconstructed by selecting the associated chunks and their edges.
---


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
- Relations linked to `ChunkNode` and `RaptorNode` for implicit versioning

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

## Development Setup
Install dependencies and set up pre-commit hooks:

```bash
pip install -r requirements.txt
pre-commit install
```

