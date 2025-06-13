from __future__ import annotations

"""Asynchronous helper around the Neo4j driver.

`GraphProxy` exposes only two high level methods: :meth:`run_query` for
executing a single Cypher statement and :meth:`run_queries` for batching
multiple statements in one transaction. Queries are routed to the appropriate
read/write endpoint and retried by the driver if a transient failure occurs.
Debug output is printed when :data:`app_settings.DEBUG` is enabled.
"""

from contextlib import AbstractAsyncContextManager
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncManagedTransaction

from config import app_settings

__all__ = ["GraphProxy"]


class GraphProxy(AbstractAsyncContextManager):
    """Client used by the pipeline to talk to Neo4j.

    The proxy wraps :class:`neo4j.AsyncDriver` and may be used as an async
    context manager. Resources are released by calling :meth:`close` or by
    leaving the ``async with`` block. All operations rely on transaction
    functions so that the driver can automatically retry on transient failures.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str | None = None,
    ) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            uri, auth=(user, password)
        )
        self._database = database

    # ------------------------------------------------------------------ utils
    @staticmethod
    async def _run(
        tx: AsyncManagedTransaction, cypher: str, params: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:  # noqa: E501
        """Internal helper executed inside a transaction function."""
        result = await tx.run(cypher, params or {})
        return [record.data() async for record in result]

    def _log(self, cypher: str, params: Optional[Dict[str, Any]]) -> None:
        if app_settings.DEBUG:
            print(">>> CYPHER", "\n", cypher, "\nPARAMS =", params, "\n<<<")

    # ----------------------------------------------------------- public api --
    async def run_query(
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
        async with self._driver.session(database=self._database) as session:
            fn = session.execute_write if write else session.execute_read
            return await fn(self._run, cypher, params)

    async def run_queries(
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

        async def batch_tx(tx: AsyncManagedTransaction) -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []
            for c, p in zip(cypher_list, params_list):
                self._log(c, p)
                results.extend(await self._run(tx, c, p))
            return results

        async with self._driver.session(database=self._database) as session:
            fn = session.execute_write if write else session.execute_read
            return await fn(batch_tx)

    # -------------------------------------------------------------- cleanup --
    async def close(self) -> None:  # noqa: D401
        """Close underlying driver (call at application shutdown)."""
        await self._driver.close()

    # -------------------------------------------------------- context-manager --
    async def __aenter__(self):  # noqa: D401
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        await self.close()


@lru_cache()
def get_graph_proxy() -> GraphProxy:
    """Create and cache a GraphProxy instance."""
    return GraphProxy(
        uri=app_settings.NEO4J_URI,
        user=app_settings.NEO4J_USER,
        password=app_settings.NEO4J_PASSWORD,
        database=app_settings.NEO4J_DB,
    )
