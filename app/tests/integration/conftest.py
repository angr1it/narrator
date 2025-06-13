import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
import weaviate


@pytest.fixture(scope="session", autouse=True)
def integration_env():
    """Load .env and set docker service defaults."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    os.environ.setdefault("WEAVIATE_URL", "http://localhost:8080")
    os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
    os.environ.setdefault("NEO4J_USER", "neo4j")
    os.environ.setdefault("NEO4J_PASSWORD", "test")
    os.environ.setdefault("NEO4J_DB", "neo4j")


@pytest.fixture(scope="session")
def wclient():
    """Connect to dockerised Weaviate."""
    client = weaviate.connect_to_local(host="localhost", port=8080, grpc_port=50051)
    yield client
    client.close()


@pytest.fixture(scope="session", name="weaviate_client")
def weaviate_client_alias(wclient):
    return wclient
