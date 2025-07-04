import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
import pytest_asyncio
import weaviate
import openai
from uuid import uuid4
from urllib.parse import urlparse
from weaviate.connect.helpers import connect_to_weaviate_cloud, connect_to_local
from services.graph_proxy import GraphProxy


@pytest.fixture(scope="session", autouse=True)
def integration_env():
    """Load .env and set docker service defaults."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    # Force local docker-compose endpoints so tests don't accidentally hit
    # remote services when `.env` specifies different hosts.
    os.environ["WEAVIATE_URL"] = "http://localhost:8080"
    os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "testtest"
    os.environ["NEO4J_DB"] = "neo4j"
    # Configure OpenAI client for integration tests
    _api_key = os.getenv("OPENAI_API_KEY")
    if _api_key:
        openai.api_key = _api_key


@pytest.fixture(scope="session")
def wclient():
    """Connect to Weaviate instance (local or remote) using environment settings."""
    url = os.getenv("WEAVIATE_URL")
    api_key = os.getenv("WEAVIATE_API_KEY")
    if api_key:
        auth = weaviate.AuthApiKey(api_key)
        client = connect_to_weaviate_cloud(cluster_url=url, auth_credentials=auth)
    else:
        # Parse host and port for local connection
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", 50051))
        client = connect_to_local(
            host=host,
            port=port,
            grpc_port=grpc_port,
            skip_init_checks=True,
        )
    yield client
    client.close()


@pytest.fixture(scope="session", name="weaviate_client")
def weaviate_client_alias(wclient):
    return wclient


@pytest.fixture(scope="session")
def openai_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    assert key, "Set OPENAI_API_KEY in environment to run integration tests"
    return key


@pytest.fixture(scope="session")
def openai_embedder(openai_key):
    def _embed(text: str) -> list[float]:
        openai.api_key = openai_key
        resp = openai.embeddings.create(
            input=text,
            model="text-embedding-3-small",
            user="integration-tests",
        )
        return resp.data[0].embedding

    return _embed


@pytest.fixture()
def temp_collection_name(wclient):
    name = f"Tmp_{uuid4().hex[:8]}"
    yield name
    if wclient.collections.exists(name):
        wclient.collections.delete(name)


@pytest.fixture()
def clean_alias_collection(wclient):
    if wclient.collections.exists("Alias"):
        wclient.collections.delete("Alias")
    yield
    if wclient.collections.exists("Alias"):
        wclient.collections.delete("Alias")


@pytest_asyncio.fixture()
async def graph_proxy():
    """Create :class:`GraphProxy` connected to the local Neo4j instance."""
    proxy = GraphProxy(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "testtest"),
        database=os.getenv("NEO4J_DB", "neo4j"),
    )
    yield proxy
    await proxy.close()
