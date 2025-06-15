from typing import List, Optional, Literal, Union
from enum import Enum
from datetime import datetime
import uuid

from pydantic import BaseModel, model_validator

from templates import env


class TemplateRenderMode(str, Enum):
    """Rendering mode for :class:`CypherTemplateBase.render`."""

    EXTRACT = "extract"
    AUGMENT = "augment"


class SlotDefinition(BaseModel):
    """
    Определение одного слота, который должен быть извлечён из текста.
    Например: character, faction, location.
    """

    name: str
    type: Literal["STRING", "INT", "FLOAT", "BOOL"]
    description: Optional[str] = None
    required: bool = True
    default: Optional[Union[str, int, float, bool]] = None
    # (опц.) признак того, что слот — это ссылка на сущность
    is_entity_ref: Optional[bool] = False


class GraphRelationDescriptor(BaseModel):
    """
    Описание типа факта, который будет зафиксирован с помощью шаблона.
    Пример: MEMBER_OF, HAS_TRAIT, OWNS_ITEM.
    """

    predicate: str  # тип связи: MEMBER_OF, HAS_TRAIT и т.д.
    subject: str  # "$character" — имя слота
    object: Optional[str] = None  # "$faction"
    value: Optional[str] = None  # строковое значение (если не object)
    details: Optional[str] = None  # chain-of-thought reasoning


class CypherTemplateBase(BaseModel):
    """
    Описание Cypher-шаблона, который превращает извлечённые слоты в запрос.
    """

    name: str  # slug шаблона
    version: str = "1.0.0"
    title: str
    description: str
    details: Optional[str] = None
    category: Optional[str] = None

    slots: dict[str, SlotDefinition]
    graph_relation: Optional[GraphRelationDescriptor] = None
    fact_policy: Literal["none", "always"] = "always"
    attachment_policy: Literal["chunk", "raptor", "both"] = "chunk"

    extract_cypher: Optional[str] = None  # путь к Jinja-файлу шаблона вставки
    use_base_extract: bool = True  # оборачивать ли через chunk_mentions.j2

    augment_cypher: Optional[str] = None
    supports_extract: Optional[bool] = None
    supports_augment: Optional[bool] = None

    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    vector: Optional[List[float]] = None

    default_confidence: float = 0.2

    return_map: dict[str, str]  # имена переменных → ноды/идентификаторы в графе

    @model_validator(mode="after")
    def _set_support_flags(self) -> "CypherTemplateBase":
        if self.supports_extract is None:
            self.supports_extract = self.extract_cypher is not None
        if self.supports_augment is None:
            self.supports_augment = self.augment_cypher is not None
        return self

    def validate_augment(self) -> None:
        """Ensure augment-related fields are consistent."""
        if self.supports_augment and not self.augment_cypher:
            raise ValueError(
                f"Template {self.name} supports augment but has no augment_cypher"
            )

    def validate_extract(self) -> None:
        """Ensure extract-related fields are consistent."""
        if self.supports_extract and not self.extract_cypher:
            raise ValueError(
                f"Template {self.name} supports extract but has no extract_cypher"
            )
        if self.use_base_extract and not self.supports_extract:
            raise ValueError(
                f"Template {self.name} sets use_base_extract without extract support"
            )

    def render(
        self,
        slots: dict,
        chunk_id: str,
        *,
        mode: TemplateRenderMode = TemplateRenderMode("extract"),
    ) -> str:
        required = [slot.name for slot in self.slots.values() if slot.required]
        missing = [name for name in required if name not in slots]
        if missing:
            raise ValueError(f"Missing required slots: {missing}")

        context = dict(slots)
        context["chunk_id"] = chunk_id

        # triple-text: semantic string used for fact_vec
        if self.graph_relation:

            def pick(expr: str | None) -> str | None:
                return slots.get(expr[1:]) if expr and expr.startswith("$") else expr

            subject = pick(self.graph_relation.subject)
            object_ = pick(self.graph_relation.object)
            context["triple_text"] = (
                f"{subject} {self.graph_relation.predicate} {object_}"
            )
            context["related_node_ids"] = [
                val for val in [subject, object_] if val is not None
            ]

        # fallback if template_id missing
        context["template_id"] = self.name

        cypher_name = (
            self.extract_cypher
            if mode is TemplateRenderMode.EXTRACT
            else self.augment_cypher
        )
        if mode is TemplateRenderMode.AUGMENT:
            self.validate_augment()
            if not self.supports_augment:
                raise ValueError(f"Template {self.name} does not support augment")
            if cypher_name is None:
                raise ValueError(f"Template {self.name} missing augment_cypher")
        else:
            self.validate_extract()
            if not self.supports_extract:
                raise ValueError(f"Template {self.name} does not support extract")
            cypher_name = self.extract_cypher
            assert cypher_name is not None
            if self.use_base_extract and not cypher_name.startswith("chunk_"):
                cypher_name = "chunk_mentions.j2"
                context["template_body"] = self.extract_cypher  # used for {% include %}

        template = env.get_template(cypher_name)
        return template.render(**context)


class CypherTemplate(CypherTemplateBase):
    id: uuid.UUID


class RenderedCypher(BaseModel):
    template_id: str
    content_cypher: str  # основная часть с MERGE
    alias_cypher: Optional[str] = None  # если нужен alias
    relation_cypher: Optional[str] = None  # ранее: fact_cypher
    triple_text: str  # строка вида "Aren MEMBER_OF Night Front"
    details: str  # отладка / chain-of-thought
