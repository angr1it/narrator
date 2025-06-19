import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetTemplateRequest(_message.Message):
    __slots__ = ("template_id",)
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    template_id: str
    def __init__(self, template_id: _Optional[str] = ...) -> None: ...

class FindTemplatesRequest(_message.Message):
    __slots__ = ("query", "category", "top_k")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    query: str
    category: str
    top_k: int
    def __init__(
        self,
        query: _Optional[str] = ...,
        category: _Optional[str] = ...,
        top_k: _Optional[int] = ...,
    ) -> None: ...

class FindTemplatesResponse(_message.Message):
    __slots__ = ("templates",)
    TEMPLATES_FIELD_NUMBER: _ClassVar[int]
    templates: _containers.RepeatedCompositeFieldContainer[_common_pb2.Template]
    def __init__(
        self,
        templates: _Optional[_Iterable[_Union[_common_pb2.Template, _Mapping]]] = ...,
    ) -> None: ...

class UpsertTemplateRequest(_message.Message):
    __slots__ = ("template",)
    TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    template: _common_pb2.Template
    def __init__(
        self, template: _Optional[_Union[_common_pb2.Template, _Mapping]] = ...
    ) -> None: ...
