from typing import List, Optional, Literal, Union
from datetime import datetime
import uuid

from pydantic import BaseModel

from templates import env


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

    cypher: str  # путь к Jinja-файлу шаблона
    use_base: bool = True  # нужно ли оборачивать через base_fact.j2

    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    vector: Optional[List[float]] = None

    default_confidence: float = 0.2

    return_map: dict[str, str]  # имена переменных → ноды/идентификаторы в графе

    def render(self, slots: dict, chunk_id: str) -> str:
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

        # optional wrapping via base_fact
        cypher_name = self.cypher
        if self.use_base and not self.cypher.startswith("base_"):
            cypher_name = "base_fact.j2"
            context["template_body"] = self.cypher  # used for {% include %}

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
