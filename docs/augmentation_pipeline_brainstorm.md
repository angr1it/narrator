# Augmentation Pipeline Brainstorm

## Service Overview

StoryGraph is a FastAPI service that processes small text fragments and updates a graph
model. Two endpoints are available:

- **`/extract-save`** — turns text into graph relations.
- **`/augment-context`** — planned endpoint to enrich text with context.

According to the main `README.md`, extraction relies on templates, LLM slot filling
and a Neo4j graph store. Weaviate provides template search and RaptorNode keeps
embeddings for clustering【F:README.md†L8-L73】.

## `/extract-save` in detail

Documentation `extract_save_algorithm.md` describes the full flow. The request
contains text, chapter and optional tags. The service saves a `ChunkNode` and uses
`TemplateService` to find relevant `CypherTemplate` objects, then `SlotFiller` to
obtain values for each slot. Alias records are stored in Weaviate, Cypher statements
are executed via `GraphProxy`, and the resulting triple text is embedded to update
`RaptorNode`【F:docs/extract_save_algorithm.md†L20-L148】.

The response returns the created `chunk_id`, the computed `raptor_node_id`,
created relationships and aliases【F:docs/extract_save_algorithm.md†L223-L236】.

## Brainstorm: implementing `augment-context`

Existing docs show only a stub for this pipeline, but `fact_examples.md` gives a
hint. It suggests using SELECT-style templates to query traits or relations from
the graph and feed the results back to the writer【F:docs/fact_examples.md†L50-L70】.

A possible design is:

1. **Template discovery** – use the same `TemplateService` but with templates that
   contain Cypher `MATCH` statements instead of `MERGE`.
2. **Slot filling** – `SlotFiller` extracts query parameters from the input
   passage (e.g. characters mentioned, chapter number).
3. **Query execution** – render the template through `TemplateRenderer` and run it
   via `GraphProxy`. Each template returns structured rows describing relevant
   facts (traits, relationships, past events).
4. **Post-processing** – gather all rows, optionally summarise them with LLM into
   short hints.
5. **Return** – send the structured context back to the client for integration in
   the editor.

This approach keeps the pipeline symmetrical with `extract-save` but replaces
`MERGE` statements with `MATCH` queries and skips the Raptor update step.

### Template Discovery and TemplateService Requirements

- The service must differentiate between creation templates (`MERGE`) and
  query templates used by `/augment-context`.
- `TemplateService.top_k` should accept a `mode` flag to filter only templates
  marked as `select`. Such templates store Cypher `MATCH` logic and a `return_schema`.
- Each template provides a minimal vector embedding, a category and an optional
  list of required tags to improve retrieval quality.

### Slot Filling Strategy

- At the augmentation stage we want to minimise LLM calls.
- `SlotFiller` can attempt deterministic extraction using previously saved alias
  data or simple regex patterns. If all required values are resolved this way, no
  LLM prompt is issued.
- When some slots are ambiguous, a light-weight LLM prompt can be used as a
  fallback, but the goal is to keep the number of prompts close to zero.

### Cypher Query Format

- Query templates consist of a `MATCH ... WHERE` block and a structured
  `RETURN` clause. The returned columns must match the `return_schema` field of
  the template so the pipeline can parse rows.
- Example:

  ```cypher
  MATCH (p:Character {id: $subject})-[:HAS_TRAIT]->(t:Trait)
  WHERE t.chapter <= $chapter
  RETURN t.name AS trait
  ```

### Post-processing and Response

- The pipeline merges rows from all templates and may request an LLM to summarise
  them into concise hints.
- The final response should contain both the raw rows and the optional summary so
  the client can decide how to display context.

## Conclusion

The service already has clear architecture for converting text to graph via
`/extract-save`. Implementing `augment-context` can reuse the same components
(TemplateService, SlotFiller, GraphProxy) but drive them with query templates to
retrieve and summarise existing story data.
