# Contracts Repository

This directory contains protobuf definitions shared across microservices. It mimics a separate repository that will be packaged and installed as a dependency.

## Structure

```
contracts/
├── buf.yaml            # buf config
├── buf.gen.yaml        # generation plugins
├── version.txt         # semantic version
├── proto/              # .proto sources
├── contracts_py/       # generated Python code
├── pyproject.toml      # Poetry package config
└── .github/workflows/
    └── build.yml       # CI for publishing
```

## Using the contracts

1. Generate code:
   ```bash
   pip install protobuf_to_pydantic[all] mypy-protobuf
   buf generate
   ```
2. Build a wheel and publish:
   ```bash
   python -m build -w
   ```
3. Install in services via Poetry or pip:
   ```bash
   poetry add contracts@<version>
   # or
   pip install contracts==<version>
   ```

## Migration steps

When moving this directory to its own repository:
1. Copy the `contracts/` folder as the repo root.
2. Enable the provided GitHub Actions workflow for building and publishing.
3. Bump `version.txt` and create a git tag to release a new version.
