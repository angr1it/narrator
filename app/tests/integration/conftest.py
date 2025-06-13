import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
import weaviate
import openai
from urllib.parse import urlparse
from weaviate.connect.helpers import connect_to_weaviate_cloud, connect_to_local


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
