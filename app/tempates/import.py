from typing import List, Union, Dict

from schemas.cypher import CypherTemplate
from services.template_service import TemplateService
from utils.logger import get_logger


logger = get_logger(__name__)


def import_templates(
    service: TemplateService, templates: List[Union[CypherTemplate, Dict]]
) -> None:
    """Bulk import a list of CypherTemplates into Weaviate."""
    for entry in templates:
        if isinstance(entry, dict):
            tpl = CypherTemplate(**entry)
        elif isinstance(entry, CypherTemplate):
            tpl = entry
        else:
            raise TypeError(f"Invalid template type: {type(entry)}")

        try:
            service.upsert(tpl)
            logger.info(f"✓ Imported template: {tpl.id}")
        except Exception as e:
            logger.warning(f"✗ Failed to import {tpl.id}: {e}")
