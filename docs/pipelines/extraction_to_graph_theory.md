# Extraction to Graph – Detailed Process

This document summarises how StoryGraph converts raw text into structured graph data. It combines details from
existing docs and highlights implementation nuances visible in the code.

---

## 1. High‑level Idea

The service receives a short passage (2–8 sentences) and stores all discovered
entities and relationships in Neo4j. Each call results in a `:Chunk` node that
ties together domain nodes, `MENTIONS` edges and a `RaptorNode` representing a
semantic cluster. Templates describe how to interpret the text, ensuring that the
resulting graph follows a consistent schema.

The approach stems from the need to maintain traceability between narrative text
and structured knowledge. Instead of creating ephemeral `Fact` nodes, the graph
stores direct relations (`MEMBER_OF`, `OWNS`, etc.) while the originating chunk
acts as a stable anchor.

---

## 2. Step‑by‑step Flow

1. **Chunk creation** – `ExtractionPipeline.extract_and_save` generates a
   deterministic `chunk_id` and inserts a `:Chunk` node with the text, chapter,
   stage and tags. See `_create_chunk` in
   `app/services/pipeline.py`.
2. **Template search** – `TemplateService.top_k_async` performs a vector search in
   Weaviate to select relevant `CypherTemplate` objects. The search uses the
   embedding of the input text and filters by template category when provided.
3. **Slot filling** – `SlotFiller.fill_slots` asks the LLM to populate the
   template’s slot schema. It supports multi‑match, fallback prompts and
   generation of optional fields. Validation casts values according to
   `SlotDefinition.type`.
4. **Alias resolution** – `IdentityService.resolve_bulk` converts raw names to
   canonical IDs and yields `AliasTask` objects. `commit_aliases` inserts
   `AliasRecord` objects in Weaviate and returns Cypher snippets for creating
   missing nodes.
5. **Cypher rendering** – `TemplateRenderer.render` merges the filled slots with
   meta information (`chunk_id`, `chapter`, `draft_stage`). The base wrapper
   `chunk_mentions.j2` injects a `MATCH (chunk)` block and `MENTIONS` edges to all
   `related_node_ids` derived from the template’s `graph_relation`.
6. **Graph execution** – `GraphProxy.run_queries` executes alias Cypher and the
   rendered domain Cypher in one transaction. Queries containing `WITH *` are
   split into two statements to avoid the `MATCH after MERGE` error in Neo4j.
7. **Raptor update** – all produced `triple_text` strings are concatenated and
   passed to `FlatRaptorIndex.insert_chunk`. The returned ID is stored on the
   `Chunk` node (`chunk.raptor_node_id`).
8. **Response** – the pipeline returns `chunk_id`, `raptor_node_id`, the list of
   created relationships and aliases for inspection.

---

## 3. TemplateService in Depth

`TemplateService` manages the library of `CypherTemplate` objects stored in
Weaviate. Each template describes one domain pattern (for example, a character
joining a faction) and references a Jinja2 file with the Cypher logic. The
service ensures that templates have a consistent schema, embeds them for vector
search and exposes a simple API for retrieval.

### Template lifecycle

- **Schema** – on initialisation the service checks that the `CypherTemplate`
  collection exists with all required properties (name, slots, cypher files,
  graph relation, return map, etc.). Vector indexing is disabled so the service
  can provide its own embeddings.
- **Upsert** – `TemplateService.upsert` validates the template, generates an
  embedding from the canonicalised `description ‖ details` text and inserts or
  updates the object in Weaviate. Built‑in templates are loaded via
  `ensure_base_templates` at startup.
- **Retrieval** – `top_k` and `top_k_async` accept a text query and optional
  category. If an embedder is configured the query is vectorised and an HNSW
  `near_vector` search is performed; otherwise the service falls back to
  `near_text`. Results with distance above the threshold are discarded and a
  warning is logged when the best match is weak.
- **Mode filter** – when called with `TemplateRenderMode.AUGMENT` an additional
  filter requires `supports_augment=True` so that extraction and augmentation
  templates share the same collection.

### How matching feeds the pipeline

The extraction pipeline calls `top_k_async` to obtain candidate templates. They
are returned in order of ascending distance. The pipeline then iterates over each
template, invokes `SlotFiller` to populate its slots and finally renders Cypher
via `TemplateRenderer`. Only templates that passed the distance threshold are
considered, keeping low‑confidence matches out of the graph.

---

## 4. Implementation Nuances

- **Stable IDs** – `chunk_id` is a SHA‑1 hash of the text. Entities resolved by
  `IdentityService` obtain deterministic UUIDs so that repeated extractions link
  to the same nodes.
- **`WITH *` splitting** – because `chunk_mentions.j2` adds a `WITH *` separator
  between MERGE and MATCH parts, `ExtractionPipeline` splits the query and sends
  the fragments sequentially via `GraphProxy`.
- **Return map** – templates define a `return_map` indicating which variables in
  Cypher correspond to node IDs. `TemplateRenderer` uses it to build a
  `RenderPlan` with `related_node_ids` for `MENTIONS` edges.
- **GraphRelationDescriptor** – templates optionally specify `subject`,
  `predicate` and `object` expressions. Their resolved values form `triple_text`
  which is embedded and blended with the text vector when creating a
  `RaptorNode`.
- **Confidence and draft stage** – `StageEnum` controls the draft phase and is
  stored on both the `Chunk` and generated relations. The default confidence for
  a template is injected during rendering to allow soft assertions.
- **Alias validation** – `IdentityService` discards invalid aliases (e.g.
  meaningless or conflicting names) before inserting them into Weaviate.
- **Slot validation** – `SlotFiller` builds a Pydantic model on the fly to ensure
  all required slots are present and correctly typed. Missing values trigger a
  fallback prompt before generation of optional fields.
- **Raptor clustering** – `FlatRaptorIndex` checks if the blended centroid is
  close to an existing vector (`distance <= 0.1`). If so, the chunk joins that
  node; otherwise a new `RaptorNode` is created.

---

## 5. Theoretical Rationale

The extraction pipeline is designed around the idea of **explicit templates** and
**graph‑first storage**:

- Templates allow the system to reason about narrative structure explicitly
  instead of relying solely on free‑form LLM output. Each template declares the
  expected slots, the Cypher to run and the semantic meaning of the relation.
- Attaching every relation to a `Chunk` preserves traceability and enables
  versioning. Since `Chunk` → `RaptorNode` is a stable link, the service can
  cluster similar passages and later aggregate them without a dedicated `Fact`
  entity.
- `IdentityService` ensures that all textual mentions resolve to canonical
  entities. Storing alias records separately allows incremental improvements of
  entity resolution without rewriting the graph.
- The combination of `text_vec` and `fact_vec` embeddings links surface text and
  semantic triples in the same space, facilitating contextual retrieval and
  similarity search.

Together these choices yield a pipeline where extraction steps are transparent,
reproducible and easily extended with new templates or embedding models.

---

## 6. Related Documents

- [pipeline_overview.md](pipeline_overview.md)
- [pipeline_implementation.md](pipeline_implementation.md)
- [extract_save_algorithm.md](extract_save_algorithm.md)
- [extract_graph_schema.md](extract_graph_schema.md)

