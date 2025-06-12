import asyncio
import os
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Единый цикл на всю pytest‑сессию — избавляет от конфликтов asyncpg."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def _set_test_env(request):
    """Set default env for unit tests; skip for integration ones."""

    if any(item for item in request.session.items if "integration" in item.keywords):
        print("Skipping environment setup for integration tests...")
        return

    defaults = {
        "OPENAI_API_KEY": "x",
        "NEO4J_URI": "bolt://example.com",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "pass",
        "NEO4J_DB": "neo4j",
        "WEAVIATE_URL": "http://localhost",
        "WEAVIATE_API_KEY": "x",
        "WEAVIATE_INDEX": "idx",
        "WEAVIATE_CLASS_NAME": "cls",
        "AUTH_TOKEN": "x",
    }

    os.environ.update(defaults)

    # yield

    # print("Cleaning up environment variables after tests...")
    # os.environ.clear()
    # os.environ.update(orig)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--runintegration",
        action="store_true",
        default=False,
        help="run integration tests (require external services)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration requiring external services",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--runintegration"):
        return
    skip_marker = pytest.mark.skip(reason="use --runintegration to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)
