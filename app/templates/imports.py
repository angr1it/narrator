from typing import List, Union, Dict

from schemas.cypher import CypherTemplateBase
from services.templates import TemplateService
from utils.logger import get_logger


logger = get_logger(__name__)


def import_templates(
    service: TemplateService, templates: List[Union[CypherTemplateBase, Dict]]
) -> None:
    """Bulk import a list of CypherTemplates into Weaviate."""
    for entry in templates:
        if isinstance(entry, dict):
            tpl = CypherTemplateBase(**entry)
        elif isinstance(entry, CypherTemplateBase):
            tpl = entry
        else:
            raise TypeError(f"Invalid template type: {type(entry)}")
        try:
            service.upsert(tpl)
            logger.info(f"✓ Imported template: {tpl.name}")
        except Exception as e:
            logger.warning(f"✗ Failed to import {tpl.name}: {e}")
