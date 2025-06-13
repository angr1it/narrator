"""GraphProxy query construction tests.

The dummy Neo4j driver allows checking that cypher queries are executed with
the correct parameters and that the context manager behaviour works.
"""

import pytest  # noqa: E402
from services.graph_proxy import GraphProxy  # noqa: E402


class DummyRecord:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data


class DummyResult:
    def __init__(self, records):
        self._records = records

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._records:
            raise StopAsyncIteration
        return self._records.pop(0)


class DummyTx:
    def __init__(self):
        self.calls = []

    async def run(self, cypher, params):
        self.calls.append((cypher, params))
        return DummyResult([DummyRecord({"ok": True})])


class DummySession:
    def __init__(self):
        self.write_calls = []
        self.read_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute_write(self, func, *args):
        tx = DummyTx()
        res = await (func(tx, *args) if args else func(tx))
        self.write_calls.extend(tx.calls)
        return res

    async def execute_read(self, func, *args):
        tx = DummyTx()
        res = await (func(tx, *args) if args else func(tx))
        self.read_calls.extend(tx.calls)
        return res


class DummyDriver:
    def __init__(self):
        self.sessions = []
        self.closed = False

    def session(self, database=None):
        sess = DummySession()
        self.sessions.append(sess)
        return sess

    async def close(self):
        self.closed = True


class DummyGraphDB:
    def __init__(self, driver):
        self._driver = driver

    def driver(self, uri, auth):
        return self._driver


@pytest.fixture
def dummy_driver(monkeypatch):
    drv = DummyDriver()
    monkeypatch.setattr(
        "services.graph_proxy.AsyncGraphDatabase",
        DummyGraphDB(drv),
    )
    yield drv


@pytest.mark.asyncio
async def test_run_query_write_and_read(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    await gp.run_query("MATCH (n)")
    await gp.run_query("MATCH (n)", write=False)
    write_sess = dummy_driver.sessions[0]
    read_sess = dummy_driver.sessions[1]
    assert write_sess.write_calls
    assert read_sess.read_calls


@pytest.mark.asyncio
async def test_run_queries_multiple(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    res = await gp.run_queries(["A", "B"], [{"a": 1}, {"b": 2}])
    session = dummy_driver.sessions[0]
    assert session.write_calls == [("A", {"a": 1}), ("B", {"b": 2})]
    assert res == [{"ok": True}, {"ok": True}]


@pytest.mark.asyncio
async def test_run_queries_param_mismatch(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    with pytest.raises(ValueError):
        await gp.run_queries(["A"], [{"a": 1}, {"b": 2}])


@pytest.mark.asyncio
async def test_context_manager_closes(dummy_driver):
    async with GraphProxy("bolt://x", "u", "p") as gp:
        await gp.run_query("MATCH (n)")
    assert dummy_driver.closed


@pytest.mark.asyncio
async def test_run_queries_read_mode(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    await gp.run_queries(["MATCH (n) RETURN 1"], write=False)
    session = dummy_driver.sessions[0]
    assert session.read_calls == [("MATCH (n) RETURN 1", {})]


@pytest.mark.asyncio
async def test_run_queries_no_params(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    await gp.run_queries(["MATCH (n) RETURN 1"])
    session = dummy_driver.sessions[0]
    assert session.write_calls == [("MATCH (n) RETURN 1", {})]


@pytest.mark.asyncio
async def test_close_method(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    await gp.close()
    assert dummy_driver.closed
