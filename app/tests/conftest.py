import os
import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def pytest_addoption(parser):
    parser.addoption(
        "--runintegration",
        action="store_true",
        default=False,
        help="run integration tests",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark integration tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runintegration"):
        return
    skip = pytest.mark.skip(reason="use --runintegration to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


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
