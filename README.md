# StoryGraph Service – Technical and Architectural Overview

This document serves as a live specification for the StoryGraph prototype. It includes a detailed breakdown of the service's functional purpose, architectural components, data flow, implementation classes, and key algorithms.
For a full list of design documents see [docs/README.md](docs/README.md).

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
- Jinja2-based Cypher templates stored in Weaviate
- Extraction and augmentation pipelines orchestrate slot filling, identity resolution and Neo4j queries
- `GraphProxy` abstraction for Cypher execution
- Relations linked to `ChunkNode` and `RaptorNode` for implicit versioning

---

## 9. Next Steps
- Integrate LLM summariser for augmentation results
- Expand unit and integration tests for both pipelines
- Finalise documentation of request/response format and tagging rules

---

## Development Setup
Install dependencies and set up pre-commit hooks:

```bash
pip install -r requirements.txt
pre-commit install
```

The protobuf schemas used for RPC communication live in the `contracts/` folder.
After moving it to a dedicated repository, install the published package and
update dependencies via Poetry:

```bash
poetry add contracts@<version>
```


## Codex Dev Environment
Для локального запуска Codex-агента и интеграционных тестов см. [docs/quickstart/codex_dev_environment.md](docs/quickstart/codex_dev_environment.md).

## Agent Quick Start
A concise checklist for any agent starting work on the project is available at [docs/quickstart/agent_quick_start.md](docs/quickstart/agent_quick_start.md). Check it before exploring other files.

