# Redesign Backlog Analysis

The document `yield_return_bug.md` describes three possible strategies for refactoring the Cypher templates and the pipeline. This note evaluates how each option fits the current implementation.

## Current state

The extraction pipeline renders templates and then splits the resulting query around `WITH *`. The code responsible for that is `_process_template` in `services.pipeline`. It looks for `WITH *` and executes the two parts sequentially:

```python
cypher = render.content_cypher
query_parts = [cypher]
if "WITH *" in cypher:
    head, tail = cypher.split("WITH *", 1)
    query_parts = [head.strip(), tail.strip()]

batch = alias_cyphers + query_parts
await self.graph_proxy.run_queries(batch)
```

This logic avoids the `MATCH after MERGE` error in Neo4j but introduces complexity.

## Options from the backlog

The backlog section in `yield_return_bug.md` outlines three alternatives:

1. **Subqueries (`CALL { ... }`)** – wrap the domain part and the `apoc.create.relationship` call in a subquery. [Lines 32–34]
2. **Separate procedure call** – split the template into a MERGE statement and a dedicated procedure invocation. [Line 35]
3. **Custom `/* SPLIT HERE */` marker** – keep the current two-query approach but replace `WITH *` with an explicit comment. [Line 36]

Below is how each approach would map to the codebase and what impact it would have.

### 1. Subqueries
- **Template changes**: remove `WITH *`, place `CALL apoc.create.relationship` inside `CALL {}` followed by `WITH a, b`.
- **Pipeline impact**: `_process_template` no longer needs to split by `WITH *`; `batch` becomes `alias_cyphers + [cypher_query]`.
- **Benefits**: Cypher reads as a single statement, order of operations guaranteed. No extra round-trip to Neo4j.
- **Drawbacks**: all templates must be rewritten; requires Neo4j ≥4.3.

### 2. Separate procedure call
- **Template changes**: domain query and procedure call stored in different files or parts.
- **Pipeline impact**: `_process_template` assembles multiple queries: `[domain_cypher, apoc_cypher, mentions_cypher]` plus aliases.
- **Benefits**: errors in the procedure can be retried independently; no implicit `YIELD` issues.
- **Drawbacks**: extra database call per template, more code to manage parameters.

### 3. Custom marker
- **Template changes**: replace `WITH *` with `/* SPLIT HERE */`.
- **Pipeline impact**: `_process_template` looks for the marker instead of `WITH *` but otherwise behaves the same.
- **Benefits**: minimal rewrite; prevents accidental splits on other `WITH *` statements.
- **Drawbacks**: keeps the split hack, still two queries per template.

## Recommendation

Subqueries (option 1) offer the cleanest separation of MERGE and procedure logic while keeping a single round-trip to the database. Although all templates must be updated, this approach scales better as the number of templates grows and avoids the complexity of manual splitting.

The custom marker (option 3) is the quickest fix but retains technical debt. Splitting the procedure into its own query (option 2) adds latency and complicates parameter handling.

Given the need for flexibility as templates evolve, migrating to subqueries strikes a balance between readability and performance.

## Implementation sketch

1. **Templates** – update each `*_v1.j2` to wrap the procedure call in `CALL {}` and remove the `WITH *` separator. `chunk_mentions.j2` should simply continue with `WITH a, b`.
2. **`TemplateRenderer`** – no code changes are required after the bug fix; rendering already returns a single string.
3. **`ExtractionPipeline._process_template`** – drop the `WITH *` split logic. The batch becomes:

   ```python
   batch = alias_cyphers + [cypher_query]
   await self.graph_proxy.run_queries(batch)
   ```

4. **Tests** – adjust unit tests to render new templates and ensure the pipeline executes the single-query batch.

This refactor reduces special cases and prepares the service for additional templates without affecting execution speed.

