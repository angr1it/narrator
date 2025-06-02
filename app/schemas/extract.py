
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ExtractRequest(BaseModel):
    """Запрос на извлечение и сохранение фактов."""

    text: str = Field(..., description="Фрагмент 2–8 предложений")
    chapter: int = Field(..., description="Номер главы (>= 1)")
    tags: Optional[List[str]] = Field(None, description="Ключевые слова")


class ExtractResponse(BaseModel):
    """Ответ API: лог успешных вставок."""

    facts: List[Dict[str, Any]]
    inserted_ids: List[str]
