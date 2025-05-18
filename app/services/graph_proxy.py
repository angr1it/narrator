
from typing import Any, Dict, List

from neo4j import GraphDatabase, Driver

from config import app_settings


class GraphProxy:
    """Коммуницирует с Neo4j (см. README §2 «GRAPH_PROXY»)."""

    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def run_query(self, cypher: str, params: Dict[str, Any] | None = None) -> List:
        """Выполняет Cypher и возвращает список записей."""
        if app_settings.DEBUG:
            print(">>> CYPHER\n", cypher, "\n<<<")

        with self._driver.session() as session:
            result = session.run(cypher, params or {})
            return [r.data() for r in result]

