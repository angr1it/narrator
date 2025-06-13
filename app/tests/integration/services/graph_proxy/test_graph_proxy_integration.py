"""GraphProxy integration tests.

These tests run against the local Neo4j container specified in
``docker-compose.yml``. They verify that the proxy correctly creates data and
removes it when requested.
"""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration

from services.graph_proxy import GraphProxy


@pytest.mark.asyncio
async def test_run_query_creates_and_deletes(graph_proxy: GraphProxy):
    node_id = f"gp_{uuid4().hex[:8]}"
    # create node
    await graph_proxy.run_query("CREATE (n:GPTest {id:$id}) RETURN n", {"id": node_id})
    result = await graph_proxy.run_query(
        "MATCH (n:GPTest {id:$id}) RETURN n.id AS id", {"id": node_id}, write=False
    )
    assert result and result[0]["id"] == node_id

    # delete and verify cleanup
    await graph_proxy.run_query(
        "MATCH (n:GPTest {id:$id}) DETACH DELETE n", {"id": node_id}
    )
    leftover = await graph_proxy.run_query(
        "MATCH (n:GPTest {id:$id}) RETURN n", {"id": node_id}, write=False
    )
    assert leftover == []


@pytest.mark.asyncio
async def test_run_queries_batch(graph_proxy: GraphProxy):
    id_a = f"a_{uuid4().hex[:8]}"
    id_b = f"b_{uuid4().hex[:8]}"
    cyphers = [
        "CREATE (a:GPBatch {id:$a})",
        "CREATE (b:GPBatch {id:$b})",
    ]
    params = [{"a": id_a}, {"b": id_b}]
    await graph_proxy.run_queries(cyphers, params)

    res = await graph_proxy.run_query(
        "MATCH (n:GPBatch) RETURN count(n) AS cnt", write=False
    )
    assert res and res[0]["cnt"] >= 2

    await graph_proxy.run_query("MATCH (n:GPBatch) DETACH DELETE n")
    cleanup = await graph_proxy.run_query("MATCH (n:GPBatch) RETURN n", write=False)
    assert cleanup == []


@pytest.mark.asyncio
async def test_run_queries_no_params(graph_proxy: GraphProxy):
    node_id = f"np_{uuid4().hex[:8]}"
    await graph_proxy.run_query("CREATE (n:GPNoParams {id:$id})", {"id": node_id})
    res = await graph_proxy.run_queries(
        ["MATCH (n:GPNoParams) RETURN count(n) AS cnt"], write=False
    )
    assert res and res[0]["cnt"] >= 1
    await graph_proxy.run_query("MATCH (n:GPNoParams) DETACH DELETE n")
    cleanup = await graph_proxy.run_query("MATCH (n:GPNoParams) RETURN n", write=False)
    assert cleanup == []
