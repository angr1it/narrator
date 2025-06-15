# /augment-context read-only violation

## Overview

This note documents the issue with the `/augment-context` endpoint. It was intended to only read data from Neo4j. However the current implementation generates Cypher that also `MERGE`s `MENTIONS` relationships which results in writes.

## Endpoint purpose
`/augment-context` is exposed in `app/api/augment/__init__.py` and delegates work to `AugmentPipeline`:

```python
@route.post("/augment-context", response_model=AugmentCtxOut)
async def augment_ctx(req: AugmentCtxIn):
    pipeline = get_augment_pipeline()
    return await pipeline.augment_context(req.text, req.chapter)
```

The pipeline searches for relevant `CypherTemplate`s, fills slots and executes the rendered query:

```python
plan = self.template_renderer.render(
    tpl, slot_fill, meta, mode=TemplateRenderMode.AUGMENT
)
cypher = plan.content_cypher
query_parts = [cypher]
if "WITH *" in cypher:
    head, tail = cypher.split("WITH *", 1)
    query_parts = [head.strip(), tail.strip()]
    result = await self.graph_proxy.run_queries(query_parts, write=False)
else:
    result = await self.graph_proxy.run_query(cypher, write=False)
```

`write=False` is supposed to route the statement to a read replica.

## Why writes happen
`CypherTemplateBase.render` previously wrapped augment queries with `chunk_mentions.j2`:

```python
if mode is TemplateRenderMode.AUGMENT:
    self.validate_augment()
    cypher_name = self.augment_cypher
```

`chunk_mentions.j2` adds `MERGE (chunk)-[:MENTIONS]->(x)` lines:

```jinja
{% include template_body %}

WITH *
MATCH (chunk:Chunk {id: "{{ chunk_id }}"})
{% for node_id in related_node_ids %}
  MATCH (x{{ loop.index }} {id: "{{ node_id }}"})
{% endfor %}
{% for node_id in related_node_ids %}
  MERGE (chunk)-[:MENTIONS]->(x{{ loop.index }})
{% endfor %}
```

In the original code all built-in augment templates used this wrapper, so every query rendered for `/augment-context` contained `MERGE` statements even though the pipeline invoked Neo4j in read mode.

## Problem statement
- `/augment-context` should be a pure read operation, returning context rows.
- Because the wrapper injects `MERGE` clauses, Neo4j receives a write query. This either fails (if executed on a read replica) or pollutes the graph with spurious `MENTIONS` edges.
- Prior implementation always included this wrapper in `templates/base.py`.

## Related code
- `AugmentPipeline` execution (read-only flag) – see [`services/pipeline.py` lines 284‑326](../app/services/pipeline.py).
- Base wrapper logic in [`CypherTemplateBase.render`](../app/schemas/cypher.py) triggered `chunk_mentions.j2` for augmentation.
- Wrapper template [`chunk_mentions.j2`](../app/templates/cypher/chunk_mentions.j2) performs the `MERGE`.
- Built-in templates defined in [`templates/base.py`](../app/templates/base.py) included this wrapper by default.

## Proposed fix
1. Do not include `chunk_mentions.j2` for augmentation queries.
2. Update unit tests to ensure rendered Cypher contains only `MATCH` statements.
3. Verify that `GraphProxy.run_query(write=False)` receives read-only Cypher.

