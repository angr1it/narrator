import os
import time
import asyncio
import requests

import pytest
from testcontainers.core.container import DockerContainer


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
    if request.config.getoption("--runintegration"):
        return
    os.environ.update(
        {
            "OPENAI_API_KEY": "x",
            "WEAVIATE_MODE": "local",
            "WEAVIATE_URL": "http://localhost",
            "WEAVIATE_API_KEY": "x",
            # …другие плейсхолдеры…
        }
    )


@pytest.fixture(scope="session", autouse=True)
def weaviate_container(request):
    if not request.config.getoption("--runintegration"):
        pytest.skip("Skipping Weaviate container")
    container = (
        DockerContainer("semitechnologies/weaviate:1.31.0")
        .with_env("AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED", "true")
        .with_env("PERSISTENCE_DATA_PATH", "/var/lib/weaviate")
        .with_exposed_ports(8080)
    )
    with container.start() as cont:
        host = cont.get_container_host_ip()
        port = cont.get_exposed_port(8080)
        url = f"http://{host}:{port}"
        os.environ["WEAVIATE_MODE"] = "local"
        os.environ["WEAVIATE_LOCAL_URL"] = url
        for _ in range(30):
            try:
                if requests.get(f"{url}/v1/.well-known/ready").status_code == 200:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Weaviate не готов")

        print(f"Weaviate запущен по адресу {url}")
        yield url
