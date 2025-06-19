from concurrent import futures
from typing import Iterable

import grpc
from google.protobuf.json_format import MessageToDict

from contracts_py import (
    template_service_pb2_grpc,
    template_service_pb2,
    common_pb2,
)
from services.templates import TemplateService, get_template_service_sync
from schemas.cypher import CypherTemplateBase, SlotDefinition


def _pb_to_model(tpl_msg: common_pb2.Template) -> CypherTemplateBase:
    data = MessageToDict(tpl_msg, preserving_proto_field_name=True)
    slots = data.pop("slots", [])
    slot_defs = {sd["name"]: SlotDefinition(**sd) for sd in slots}
    data["slots"] = slot_defs
    data.pop("id", None)
    return CypherTemplateBase(**data)


def _model_to_pb(tpl) -> common_pb2.Template:
    msg = common_pb2.Template(
        id=str(tpl.id),
        name=tpl.name,
        title=tpl.title,
        description=tpl.description,
        category=tpl.category or "",
        keywords=tpl.keywords or [],
    )
    for slot in tpl.slots.values():
        msg.slots.add(
            name=slot.name,
            type=slot.type,
            required=slot.required,
            description=slot.description or "",
            is_entity_ref=slot.is_entity_ref or False,
            entity_type=slot.entity_type or "",
            default_value=str(slot.default) if slot.default is not None else "",
        )
    return msg


class TemplateServiceServicer(template_service_pb2_grpc.TemplateServiceServicer):
    def __init__(self, svc: TemplateService):
        self.svc = svc

    def GetTemplate(self, request, context):
        tpl = self.svc.get(request.template_id)
        return _model_to_pb(tpl)

    def FindTemplates(self, request, context):
        templates = self.svc.top_k(
            request.query,
            category=request.category or None,
            k=request.top_k or 10,
        )
        resp = template_service_pb2.FindTemplatesResponse()
        resp.templates.extend([_model_to_pb(t) for t in templates])
        return resp

    def UpsertTemplate(self, request, context):
        tpl_model = _pb_to_model(request.template)
        saved = self.svc.upsert(tpl_model)
        return _model_to_pb(saved)


def serve(port: int = 50051) -> Iterable[grpc.Server]:
    svc = get_template_service_sync()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    template_service_pb2_grpc.add_TemplateServiceServicer_to_server(
        TemplateServiceServicer(svc), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    return server


if __name__ == "__main__":
    srv = serve()
    try:
        srv.wait_for_termination()
    except KeyboardInterrupt:
        srv.stop(0)
