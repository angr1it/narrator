# Agent Quick Start

This short guide describes the minimal steps for Codex and local agents to start working with the repository.

## 1. Read project overview
- `README.md` – main architecture and pipeline description
- `docs/service_structure.md` – directory layout and file purpose
- `docs/pipeline_overview.md` – high level pipeline

## 2. Prepare environment
1. Copy `.env.example` to `.env` and fill in credentials
2. Start the API: `docker compose up -d`
   - For integration tests, run `docker compose --profile integration up -d` to
     launch Weaviate and Neo4j
3. Install Python requirements: `pip install -r requirements.txt`
4. Install pre-commit hooks: `pre-commit install`

## 3. Useful commands
- Run formatting and checks: `pre-commit run --all-files`
- Run unit tests: `pytest -q`
- Run tests with coverage: `pytest --cov=app --cov-report=xml:coverage.xml --cov-report=html --cov-fail-under=85 -q`
- Run integration tests: `pytest --runintegration -q`

This document is referenced from the repository root `README.md`.
