from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SlotDefinition(_message.Message):
    __slots__ = (
        "name",
        "type",
        "required",
        "description",
        "is_entity_ref",
        "entity_type",
        "default_value",
    )
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IS_ENTITY_REF_FIELD_NUMBER: _ClassVar[int]
    ENTITY_TYPE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: str
    required: bool
    description: str
    is_entity_ref: bool
    entity_type: str
    default_value: str
    def __init__(
        self,
        name: _Optional[str] = ...,
        type: _Optional[str] = ...,
        required: bool = ...,
        description: _Optional[str] = ...,
        is_entity_ref: bool = ...,
        entity_type: _Optional[str] = ...,
        default_value: _Optional[str] = ...,
    ) -> None: ...

class Template(_message.Message):
    __slots__ = ("id", "name", "title", "description", "category", "keywords", "slots")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    KEYWORDS_FIELD_NUMBER: _ClassVar[int]
    SLOTS_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    title: str
    description: str
    category: str
    keywords: _containers.RepeatedScalarFieldContainer[str]
    slots: _containers.RepeatedCompositeFieldContainer[SlotDefinition]
    def __init__(
        self,
        id: _Optional[str] = ...,
        name: _Optional[str] = ...,
        title: _Optional[str] = ...,
        description: _Optional[str] = ...,
        category: _Optional[str] = ...,
        keywords: _Optional[_Iterable[str]] = ...,
        slots: _Optional[_Iterable[_Union[SlotDefinition, _Mapping]]] = ...,
    ) -> None: ...
