from typing import List, Union, Dict

from schemas.cypher import CypherTemplateBase
from services.templates import TemplateService, CypherTemplate
from utils.logger import get_logger


logger = get_logger(__name__)


def import_templates(
    service: TemplateService, templates: List[Union[CypherTemplateBase, Dict]]
) -> None:
    """Import templates ensuring version-aware updates.

    For each template the helper checks if an object with the same ``name``
    already exists in the service.  If not found, the template is inserted.
    If the existing template has a different ``version``, it is overwritten via
    :meth:`TemplateService.upsert`.  When both ``name`` and ``version`` match,
    the import is skipped.
    """

    for entry in templates:
        if isinstance(entry, dict):
            tpl = CypherTemplateBase(**entry)
        elif isinstance(entry, CypherTemplateBase):
            tpl = entry
        else:
            raise TypeError(f"Invalid template type: {type(entry)}")

        tpl.validate_augment()

        try:
            existing: CypherTemplate | None
            try:
                existing = service.get_by_name(tpl.name)
            except Exception:
                existing = None

            if existing is None:
                service.upsert(tpl)
                logger.info(f"✓ Imported template: {tpl.name}")
            elif existing.version != tpl.version:
                service.upsert(tpl)
                logger.info(f"✓ Updated template: {tpl.name} → version {tpl.version}")
            else:
                logger.info(f"- Skipped template: {tpl.name} (up to date)")
        except Exception as exc:
            logger.warning(f"✗ Failed to import {tpl.name}: {exc}")
