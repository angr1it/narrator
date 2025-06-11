import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Единый цикл на всю pytest‑сессию — избавляет от конфликтов asyncpg."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
