import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def unit_test_env():
    """Default environment for unit tests."""
    defaults = {
        "OPENAI_API_KEY": "x",
        "NEO4J_URI": "bolt://example.com",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "pass",
        "NEO4J_DB": "neo4j",
        "WEAVIATE_URL": "http://localhost",
        "WEAVIATE_API_KEY": "x",
        "WEAVIATE_CLASS_NAME": "cls",
        "AUTH_TOKEN": "x",
    }
    os.environ.update(defaults)
