# Proto Contracts for TemplateService

This directory holds protobuf definitions used by the main application when communicating with the standalone `template_service`.

## Layout
- `contracts/` – message definitions (`Template`, `SlotDefinition`, etc.)
- `services/` – gRPC service definitions

## Generating Python classes
Run `protoc` with the `--python_out` and `--grpc_python_out` options:

```bash
python -m grpc_tools.protoc \
    -Iproto \
    --python_out=./proto_gen \
    --grpc_python_out=./proto_gen \
    proto/services/template_service.proto
```

The generated files can be imported from `proto_gen`.
