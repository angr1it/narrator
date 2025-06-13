import asyncio
import os

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
