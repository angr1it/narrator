from typing import List, Optional, Literal, Union
from datetime import datetime
import uuid

from pydantic import BaseModel, Field

from templates import TEMPLATE_DIR, env, TemplateNotFound


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


class FactDescriptor(BaseModel):
    """
    Описание типа факта, который будет зафиксирован с помощью шаблона.
    Пример: MEMBER_OF, HAS_TRAIT, OWNS_ITEM.
    """

    predicate: str  # e.g. "MEMBER_OF"
    subject: str  # e.g. "$character"
    value: str  # e.g. "$faction"
    object: Optional[str] = None  # e.g. "$faction"


class CypherTemplateBase(BaseModel):
    """
    Описание Cypher-шаблона, который превращает извлечённые слоты в запрос.
    """

    name: str = Field(..., description="Уникальный slug шаблона")
    version: str = "1.0.0"
    title: str
    description: str
    details: Optional[str] = None
    category: Optional[str] = None
    slots: dict[str, SlotDefinition]
    fact_descriptor: Optional[FactDescriptor] = None
    fact_policy: Literal["none", "auto", "always"] = "auto"
    cypher: str
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    vector: Optional[List[float]] = None

    def render(self, slots: dict) -> str:
        """Рендерит шаблон Cypher на основе переданных значений слотов."""
        required = [slot.name for slot in self.slots.values() if slot.required]
        missing = [name for name in required if name not in slots.keys()]

        if missing:
            raise ValueError(f"Missing required slots: {missing}")

        context = dict(slots)
        if self.fact_descriptor:
            fd = self.fact_descriptor

            def pick(expr: str | None) -> str | None:
                """resolve “$slotName” → actual value or None"""
                if expr and expr.startswith("$"):
                    return slots.get(expr[1:])
                return expr

            context["fact"] = {
                "predicate": fd.predicate,
                "subject": pick(fd.subject),
                "object": pick(fd.object),
                "value": pick(fd.value),
            }
        try:
            template = env.get_template(self.cypher)
        except TemplateNotFound:
            raise ValueError(
                f"Template file '{self.cypher}' not found in {TEMPLATE_DIR}"
            )

        return template.render(**context)


class CypherTemplate(CypherTemplateBase):
    id: uuid.UUID


class RenderedCypher(BaseModel):
    template_id: str
    content_cypher: str
    alias_cypher: Optional[str] = None  # None если алиас не нужен
    fact_cypher: Optional[str] = None  # None если факт не нужен
    triple_text: str  # "Aren MEMBER_OF Night Front"
    details: str  # chain-of-thought / debug
