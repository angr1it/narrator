# Extraction Pipeline Implementation

This document complements `pipeline_overview.md` and describes how the
`ExtractionPipeline` class performs the end-to-end flow after the
refactor that removed `FactNode`.

## Steps

1. **Chunk creation**
   - `ExtractionPipeline.extract_and_save` generates a `chunk_id` and
     inserts a `:Chunk` node with chapter, stage and text.

2. **Template discovery**
   - `TemplateService.top_k` performs a semantic vector search over
     stored `CypherTemplate` objects and returns the best matches.

3. **Slot filling**
   - `SlotFiller.fill_slots` uses the template's schema to ask the LLM
     for values. Only the first fill is used in the basic pipeline.

4. **Alias resolution**
   - `IdentityService.resolve_bulk` converts raw entity mentions to
     canonical IDs and returns `AliasTask` objects.
   - `commit_aliases` immediately saves `AliasRecord` objects in
     Weaviate and returns Cypher snippets for creating missing entities.

5. **Cypher rendering & execution**
   - `TemplateRenderer.render` merges the slot dictionary with meta
     information (`chunk_id`, `chapter`, etc.).
  - The domain template is rendered through `chunk_mentions.j2` which adds a
    `MATCH (chunk)` statement and `MENTIONS` edges.
  - If the resulting Cypher contains ``WITH *``, the pipeline splits it into two
    statements so that `MERGE` operations run before reads. Both statements and
    any alias Cypher are executed in one transaction.

6. **Raptor index update**
   - All generated `triple_text` strings are concatenated and passed to
     `FlatRaptorIndex.insert_chunk` together with the original text.
   - The returned `raptor_node_id` is stored on the `Chunk` node.

The pipeline therefore leaves the graph in a state where every created
relation is directly attached to the originating `ChunkNode` and the
chunk is linked to a semantic cluster represented by `RaptorNode`.
