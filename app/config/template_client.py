from __future__ import annotations

from functools import lru_cache
from typing import List

import grpc
from google.protobuf.json_format import MessageToDict

import sys
from pathlib import Path

PROTO_DIR = Path(__file__).resolve().parents[2] / "template_service" / "app" / "proto"
if str(PROTO_DIR) not in sys.path:
    sys.path.insert(0, str(PROTO_DIR))

from common_pb2 import Template as TemplateMsg
from template_service_pb2 import FindTemplatesRequest
from template_service_pb2_grpc import TemplateServiceStub
from schemas.cypher import CypherTemplate, SlotDefinition
from config import app_settings


class TemplateServiceClient:
    """Asynchronous gRPC client for TemplateService."""

    def __init__(self, address: str) -> None:
        self._channel = grpc.aio.insecure_channel(address)
        self._stub = TemplateServiceStub(self._channel)

    async def find_templates(
        self, query: str, *, category: str | None = None, top_k: int = 10
    ) -> List[CypherTemplate]:
        request = FindTemplatesRequest(query=query, top_k=top_k)
        if category:
            request.category = category
        response = await self._stub.FindTemplates(request)
        return [self._pb_to_model(t) for t in response.templates]

    async def close(self) -> None:
        await self._channel.close()

    @staticmethod
    def _pb_to_model(msg: TemplateMsg) -> CypherTemplate:
        data = MessageToDict(msg, preserving_proto_field_name=True)
        slots = data.pop("slots", [])
        slot_defs = {sd["name"]: SlotDefinition(**sd) for sd in slots}
        data["slots"] = slot_defs
        return CypherTemplate(**data)


@lru_cache(maxsize=1)
def get_template_service_client() -> TemplateServiceClient:
    return TemplateServiceClient(app_settings.TEMPLATE_SERVICE_ADDRESS)
