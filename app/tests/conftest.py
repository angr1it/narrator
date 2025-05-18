import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Единый цикл на всю pytest‑сессию — избавляет от конфликтов asyncpg."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
