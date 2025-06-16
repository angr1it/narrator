# GraphProxy

`GraphProxy` is a thin asynchronous wrapper around the official Neo4j driver. It
provides helper methods for executing Cypher statements and is used throughout
`ExtractionPipeline` when persisting nodes and relations.

## Features

- Uses `neo4j.AsyncDriver` and automatically retries transient failures via
  transaction functions.
- `run_query` executes a single statement, optionally routed to a read replica.
- `run_queries` executes several statements inside one transaction ensuring
  atomicity.
- Debug logging is enabled when `app_settings.DEBUG` is `True`.

## Basic usage

```python
from services.graph_proxy import GraphProxy

async with GraphProxy(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="testtest",
    database="neo4j",
) as gp:
    await gp.run_query("CREATE (:Tmp {id:$id})", {"id": "42"})
```

Instances can also be created via :func:`get_graph_proxy` which reads the
connection details from `app_settings`.

## Integration tests

`app/tests/integration/services/graph_proxy/test_graph_proxy_integration.py`
verifies that the proxy can create and remove data using a local Neo4j instance
started by `docker compose`.
