import pytest  # noqa: E402
from services.graph_proxy import GraphProxy  # noqa: E402


class DummyRecord:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data


class DummyTx:
    def __init__(self):
        self.calls = []

    def run(self, cypher, params):
        self.calls.append((cypher, params))
        return [DummyRecord({"ok": True})]


class DummySession:
    def __init__(self):
        self.write_calls = []
        self.read_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute_write(self, func, *args):
        tx = DummyTx()
        res = func(tx, *args) if args else func(tx)
        self.write_calls.extend(tx.calls)
        return res

    def execute_read(self, func, *args):
        tx = DummyTx()
        res = func(tx, *args) if args else func(tx)
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

    def close(self):
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
        "services.graph_proxy.GraphDatabase",
        DummyGraphDB(drv),
    )
    yield drv


def test_run_query_write_and_read(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    gp.run_query("MATCH (n)")
    gp.run_query("MATCH (n)", write=False)
    write_sess = dummy_driver.sessions[0]
    read_sess = dummy_driver.sessions[1]
    assert write_sess.write_calls
    assert read_sess.read_calls


def test_run_queries_multiple(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    res = gp.run_queries(["A", "B"], [{"a": 1}, {"b": 2}])
    session = dummy_driver.sessions[0]
    assert session.write_calls == [("A", {"a": 1}), ("B", {"b": 2})]
    assert res == [{"ok": True}, {"ok": True}]


def test_run_queries_param_mismatch(dummy_driver):
    gp = GraphProxy("bolt://x", "u", "p")
    with pytest.raises(ValueError):
        gp.run_queries(["A"], [{"a": 1}, {"b": 2}])


def test_context_manager_closes(dummy_driver):
    with GraphProxy("bolt://x", "u", "p") as gp:
        gp.run_query("MATCH (n)")
    assert dummy_driver.closed
