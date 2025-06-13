import pytest, os, certifi, weaviate


@pytest.fixture(scope="session")
def wclient(tmp_path_factory):
    """Embedded Weaviate в тестах без ручного скачивания бинарника."""
    data_dir = tmp_path_factory.mktemp("wdata")

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())

    with weaviate.connect_to_embedded(
        persistence_data_path=str(data_dir),
    ) as client:
        yield client
