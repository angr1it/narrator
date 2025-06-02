"""
app/services/slot_filler.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Компонент SlotFiller ― «клей» между текстом и CypherTemplate.

• Получает текст + CypherTemplate
• Прогоняет 3 фазы (extract → fallback → generate)
• Возвращает **список** заполнений вида
  {
    "template_id": "...",
    "slots": {...},       # готово для template.render()
    "details": "chain-of-thought"
  }

Использует:
  – LangChain + OpenAI (Structured JSON)
  – Jinja2 для промптов (app/prompts/*.j2)
  – Pydantic для строгой валидации
  – (опц.) Langfuse для трассировки

Шаблоны-промпты ожидают переменные:
  • template      (CypherTemplate, нужен description и др.)
  • text          (сырой фрагмент)
  • slots         (List[SlotDefinition])
  • slot_names    (List[str])
  • previous      (список объектов из прошлой фазы)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import langfuse
import openai
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, ValidationError, create_model, RootModel

from core.slots.prompts import PROMPTS_ENV
from schemas.cypher import CypherTemplate, RenderedCypher
from utils.logger import get_logger


logger = get_logger(__name__)



# Преобразование строковых типов из SlotDefinition → реальные Python-типы
TYPE_MAP = {
    "STRING": str,
    "INT": int,
    "FLOAT": float,
    "BOOL": bool,
}

from pydantic import BaseModel, Field
from typing import Optional, List

def build_slot_model(template: CypherTemplate) -> type[BaseModel]:
    fields = {
        slot.name: (TYPE_MAP[slot.type], Field(description=slot.description or "..."))
        for slot in template.slots.values()
    }
    fields["details"] = (str, Field(description="Как извлечены значения"))
    return create_model("ResponseItem", **fields)

# ──────────────────────────────────────────────────────────────────────────────
# SlotFiller
# ──────────────────────────────────────────────────────────────────────────────
class SlotFiller:
    """Класс, извлекающий / дополняющий значения слотов с помощью LLM."""

    # ------------------------------------------------------------------ init --
    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.2,
        langfuse_client: Optional[langfuse.Langfuse] = None,
    ):
        """
        Parameters
        ----------
        api_key : str
            OpenAI API-ключ.
        model_name : str
            Название модели (по умолчанию gpt-4o-mini).
        temperature : float
            Температура для LLM (низкая, чтобы быть детерминированным).
        langfuse_client : Optional[langfuse.Langfuse]
            Необязательный клиент Langfuse для трассировки.
        """
        openai.api_key = api_key
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            openai_api_key=api_key,
        )
        self.tracer = langfuse_client

    def fill_slots(self, template: CypherTemplate, text: str) -> List[Dict[str, Any]]:
        """
        Главный метод, вызываемый из ExtractionPipeline.

        Returns
        -------
        List[Dict[str, Any]]
            Список заполнений (может быть пустым).
        """
        fillings = self._run_phase(
            phase="extract",
            prompt_file="extract_slots.j2",
            template=template,
            text=text,
        )

        if self._needs_fallback(fillings, template):
            fillings = self._run_phase(
                phase="fallback",
                prompt_file="fallback_slots.j2",
                template=template,
                text=text,
                previous=fillings,
            )

        fillings = self._run_phase(
            phase="generate",
            prompt_file="generate_slots.j2",
            template=template,
            text=text,
            previous=fillings,
        )

        validated: List[Dict[str, Any]] = []
        for item in fillings:
            try:
                validated.append(
                    {
                        "template_id": template.id,
                        "slots": self._validate_and_cast(item, template),
                        "details": item.get("details", ""),
                    }
                )
            except (ValueError, ValidationError):
                # Пропускаем невалидный объект, но можно логировать
                continue

        return validated

    def fill_and_render(self, template: CypherTemplate,
                        text: str, meta: dict) -> list[RenderedCypher]:

        # 1️⃣  extraction (как раньше) → slots_raw
        fillings = self._extract_slots(template, text)

        rendered: list[RenderedCypher] = []
        for s in fillings:
            # 2️⃣  alias-resolve
            for slot_name, val in s.items():
                if slot_name in ALIASABLE:        # character, faction, ...
                     s[slot_name] = self.identity.resolve(val, slot_name, meta)

            content_cypher = template.render(s | meta)

            need_fact = (
                 template.fact_policy == "always" or
                 template.fact_policy == "auto"
                 and self._should_version_llm(text, template, s)
            )
            fact_cypher = None
            if need_fact:
                fact_cypher = self._render_versioned_fact(template, s, meta)

            # 5️⃣  триплет-строка для triple_vec
            desc = template.fact_descriptor
            triple = f"{s[desc.subject[1:]]} {desc.predicate} " \
                     f"{s.get(desc.object[1:], s.get(desc.value[1:],''))}"

            rendered.append(
                RenderedCypher(
                    template_id = template.id,
                    content_cypher = content_cypher,
                    fact_cypher    = fact_cypher,
                    triple_text    = triple,
                    details        = s.get("details","")
                )
            )
        return rendered

    def _run_phase(
        self,
        phase: str,
        prompt_file: str,
        template: CypherTemplate,
        text: str,
        previous: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Общий метод для трёх фаз (extract / fallback / generate).
        """
        if phase != "extract" and not self._needs_fallback(previous, template):
            return previous or []

        slot_names = [s.name for s in template.slots.values()]

        ItemModel = build_slot_model(template)

        # 2. Обёртка для списка
        class ResponseList(RootModel[List[ItemModel]]):
            pass

        parser = PydanticOutputParser(pydantic_object=ResponseList)
        format_instructions = parser.get_format_instructions()

        # 2. Рендерим Jinja-промпт
        tpl = PROMPTS_ENV.get_template(prompt_file)
        rendered = tpl.render(
            template=template,
            text=text,
            slots=template.slots.values(),
            slot_names=slot_names,
            previous=previous,
        )

        # 3. Создаём LangChain Prompt
        prompt = PromptTemplate(
            template=rendered + "\n\n{format_instructions}",
            input_variables=["format_instructions"],
            partial_variables={"format_instructions": format_instructions},
        )

        chain = prompt | self.llm | parser

        # 4. Запускаем цепочку с Langfuse
        span = self.tracer.span(name=f"slotfiller.{phase}") if self.tracer else None
        try:
            result = chain.invoke({})
        except Exception:
            try:
                result = chain.invoke({})
            except Exception as e:
                logger.error(f"Error in phase {phase}: {str(e)}")
                raise
        finally:
            if span:
                span.end()
    
        return result.model_dump()

    @staticmethod
    def _needs_fallback(
        fillings: Optional[List[Dict[str, Any]]], template: CypherTemplate
    ) -> bool:
        """True, если хотя бы один объект не содержит всех обязательных слотов."""
        if not fillings:
            return True
        required = {s.name for s in template.slots.values() if s.required}
        for obj in fillings:
            if not required.issubset(obj.keys()):
                return True
        return False

    def _validate_and_cast(
        self, obj: Dict[str, Any], template: CypherTemplate
    ) -> Dict[str, Any]:
        """
        Строго валидирует объект через динамическую Pydantic-модель
        и приводит типы согласно SlotDefinition.type.
        """
        # 1) строим динамическую Pydantic-схему
        fields = {
            s.name: (TYPE_MAP[s.type], ... if s.required else None)
            for s in template.slots.values()
        }
        DynamicModel: type[BaseModel] = create_model("DynamicSlotsModel", **fields)  # type: ignore

        # 2) фильтруем только нужные ключи (лишние игнорируем)
        filtered = {k: obj.get(k) for k in fields.keys() if k in obj}

        # 3) валидация + автоматический каст типов
        validated: BaseModel = DynamicModel(**filtered)
        return validated.model_dump()
