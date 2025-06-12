from __future__ import annotations

"""GraphProxy — thin convenience wrapper around the official Neo4j Python
   driver.  It provides single-query and batched execution helpers with
   automatic retry semantics, read/write separation, and optional debug
   logging controlled by `app_settings.DEBUG`.
"""

from contextlib import AbstractContextManager
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from neo4j import Driver, GraphDatabase, ManagedTransaction, Transaction

from config import app_settings

__all__ = ["GraphProxy"]


class GraphProxy(AbstractContextManager):
    """Communicates with Neo4j (see README §2 «GRAPH_PROXY»).

    Notes
    -----
    * Uses *transaction functions* (`execute_read` / `execute_write`) so the
      driver can transparently retry transient failures (e.g. leader switch).
    * Supports *batched* execution of several Cypher statements inside a single
      transaction (`run_queries`).
    * Provides a minimal context-manager interface allowing ``with`` usage.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str | None = None,
    ) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _run(
        tx: ManagedTransaction, cypher: str, params: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:  # noqa: E501
        """Internal helper executed inside a transaction function."""
        result = tx.run(cypher, params or {})
        return [record.data() for record in result]

    def _log(self, cypher: str, params: Optional[Dict[str, Any]]) -> None:
        if app_settings.DEBUG:
            print(">>> CYPHER", "\n", cypher, "\nPARAMS =", params, "\n<<<")

    # ----------------------------------------------------------- public api --
    def run_query(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        write: bool = True,
    ) -> List[Dict[str, Any]]:
        """Execute a *single* Cypher statement and return list[dict].

        Parameters
        ----------
        cypher : str
            The Cypher query string.
        params : dict | None, optional
            Parameters bound to the query.
        write : bool, default ``True``
            If ``False`` the statement is routed to a *read* replica.
        """
        self._log(cypher, params)
        with self._driver.session(database=self._database) as session:
            fn = session.execute_write if write else session.execute_read
            return fn(self._run, cypher, params)

    def run_queries(
        self,
        cyphers: Iterable[str],
        params_list: Optional[Iterable[Optional[Dict[str, Any]]]] = None,
        *,
        write: bool = True,
    ) -> List[Dict[str, Any]]:
        """Execute *multiple* Cypher statements in a single transaction.

        All statements are executed sequentially; if any fails the entire
        transaction is rolled back.  ``params_list`` must be the same length
        as ``cyphers`` or ``None`` (⇢ no parameters).
        """
        cypher_list = list(cyphers)
        params_list = list(params_list or [None] * len(cypher_list))
        if len(cypher_list) != len(params_list):
            raise ValueError("params_list length mismatch with cyphers")

        def batch_tx(tx: ManagedTransaction) -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []
            for c, p in zip(cypher_list, params_list):
                self._log(c, p)
                results.extend(self._run(tx, c, p))
            return results

        with self._driver.session(database=self._database) as session:
            fn = session.execute_write if write else session.execute_read
            return fn(batch_tx)

    # -------------------------------------------------------------- cleanup --
    def close(self) -> None:  # noqa: D401
        """Close underlying driver (call at application shutdown)."""
        self._driver.close()

    # -------------------------------------------------------- context-manager --
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401
        self.close()


@lru_cache()
def get_graph_proxy() -> GraphProxy:
    """Create and cache a GraphProxy instance."""
    return GraphProxy(
        uri=app_settings.NEO4J_URI,
        user=app_settings.NEO4J_USER,
        password=app_settings.NEO4J_PASSWORD,
        database=app_settings.NEO4J_DB,
    )
