# Augmentation Pipeline Brainstorm

## Service Overview

StoryGraph is a FastAPI service that processes small text fragments and updates a graph
model. Two endpoints are available:

- **`/extract-save`** — turns text into graph relations.
- **`/augment-context`** — endpoint to enrich text with context.

## Current status

The extraction flow is fully implemented. Work on augmentation has begun:

- `CypherTemplateBase` now defines `augment_cypher` and
  `supports_augment` fields.
- `TemplateService.top_k` accepts a `mode` flag to filter templates for
  augmentation.
- Query templates with `_aug_v1.j2` suffix provide MATCH statements and share
  the partials `_augment_filters.j2` and `_augment_meta.j2`.
 - `IdentityService` respects the `is_entity_ref` flag when resolving aliases.

`AugmentPipeline` now orchestrates template search, slot filling and query execution
and is wired to the API.

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

## Planned refactoring

Work on the augmentation pipeline surfaced several issues with how Chain-of-
Thought (CoT) explanations are stored.

1. **Domain edges lack details.** Relationships like `MEMBER_OF` are created
   without the `details` produced during slot filling. The
   `GraphRelationDescriptor.details` field already exists but is ignored. The
   renderer should pass `SlotFill.details` into the descriptor and templates must
   write this value to the domain relationship.
2. **Alias decisions lose context.** The prompt `verify_alias_llm.j2` returns a
   justification string, however :class:`IdentityService` drops it when creating
   alias tasks. This information should be stored on `AliasRecord` and when a
   new entity is created — as a property of that node.
3. **`chunk_mentions.j2` conflates chunk linkage and domain data.** This template
   currently adds `triple_text` and `details` onto `MENTIONS` edges
   【F:app/templates/cypher/chunk_mentions.j2†L1-L11】. To separate concerns it will be
   renamed to `chunk_mentions.j2` and keep only the `MATCH`/`MERGE` logic linking
   entities with the originating chunk.
4. **Shared descriptor snippet.** Domain templates repeat boilerplate to add
   `template_id`, `chapter` and future `details` to relationships. A small Jinja
   partial can expose fields from `GraphRelationDescriptor` so that domain
   templates simply include it.

These changes will allow CoT details to be retrieved from the graph and make the
pipeline auditable.

## Implemented refactoring

The following components were updated during the recent refactor:

### TemplateService
- Loads built‑in templates at startup using `ensure_base_templates`.
- Weaviate schema now includes `augment_cypher` and
  `supports_augment`.
- `top_k` and `top_k_async` accept :class:`TemplateRenderMode` to filter
  augmentation templates.

### CypherTemplate
- `render` accepts :class:`TemplateRenderMode` and validates augment fields.
- Base wrapper `chunk_mentions.j2` can be disabled in extract mode via
  `use_base_extract`.

### IdentityService
- `resolve_bulk` now takes slot definitions and skips slots where
  `is_entity_ref` is ``False``.

### Templates
- Added augment query files with `_aug_v1.j2` suffix.
- Shared partials `_augment_filters.j2` and `_augment_meta.j2` reduce
  boilerplate.

### Tests
- Unit tests cover augment rendering, template import and top‑k filtering.

## Next steps

The pipeline runs end-to-end. Remaining tasks focus on polishing:

1. Integrate a summariser to condense returned rows.
2. Expand unit and integration tests.
3. Finalise request/response documentation and tagging rules for templates.
