# Template Service

This directory contains an initial extraction of the existing `TemplateService` from
Narrator. It will become a standalone microservice responsible for managing and
searching `CypherTemplate` objects stored in Weaviate.

## Purpose
- Store Cypher templates with metadata
- Provide CRUD operations and vector search
- Serve as a separate Docker container in the future

## Repository layout
```
template_service/
├── app/                  # source code package
│   ├── config/           # service settings and clients
│   ├── services/         # TemplateService implementation
│   ├── templates/        # Jinja2 templates and import helpers
│   ├── schemas/          # Pydantic models used internally
│   ├── utils/            # logging and helpers
│   └── tests/            # unit and integration tests
├── Dockerfile            # build image for the service
├── requirements.txt      # python dependencies
├── pytest.ini            # pytest configuration
├── mypy.ini              # type checking config
└── .pre-commit-config.yaml
```

## Local development
1. Install requirements
   ```bash
   pip install -r requirements.txt
   ```
2. Install pre-commit hooks
   ```bash
   pre-commit install
   ```
3. Run checks
   ```bash
   pre-commit run --all-files
   ```
   This executes formatting, `flake8`, `mypy` and `pytest` with coverage just like
   in the main repository.

The infrastructure mirrors the one in `narrator/` so that the service can be
split out into a dedicated repository without changes.

## gRPC interface

The service exposes a gRPC API defined in `proto/`.
Run the server locally with:

```bash
python -m app.server
```

Available RPC methods:
* `GetTemplate` – return a template by ID
* `FindTemplates` – semantic search for templates
* `UpsertTemplate` – create or update a template

Clients should import message classes from the shared `contracts` package:

```python
import grpc
from contracts_py import template_service_pb2, template_service_pb2_grpc

async def search(text: str):
    async with grpc.aio.insecure_channel("localhost:50051") as ch:
        stub = template_service_pb2_grpc.TemplateServiceStub(ch)
        resp = await stub.FindTemplates(
            template_service_pb2.FindTemplatesRequest(query=text, top_k=3)
        )
        return resp.templates
```
