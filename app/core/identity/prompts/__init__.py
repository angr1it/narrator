from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from utils.helpers.cypher import cypher_escape
from utils.logger import get_logger

logger = get_logger(__name__)

PROMPT_DIR = Path(__file__).parent / "jinja"
logger.debug("PROMPT_DIR: %s", PROMPT_DIR)

PROMPTS_ENV = Environment(
    loader=FileSystemLoader(PROMPT_DIR),
    autoescape=select_autoescape(),
    undefined=StrictUndefined,
    finalize=cypher_escape,
)
