"""Generated proto modules."""

import importlib
import sys

for _mod in [
    "common_pb2",
    "common_pb2_grpc",
    "template_service_pb2",
    "template_service_pb2_grpc",
]:
    if f"contracts_py.{_mod}" not in sys.modules:
        importlib.import_module(f"contracts_py.{_mod}")
    sys.modules.setdefault(_mod, sys.modules[f"contracts_py.{_mod}"])
