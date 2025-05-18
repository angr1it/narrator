from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

PROMPT_DIR = Path(__file__).parent / "jinja"
print(f"PROMPT_DIR: {PROMPT_DIR}")

PROMPTS_ENV = Environment(
    loader=FileSystemLoader(PROMPT_DIR),
    autoescape=select_autoescape(),
    undefined=StrictUndefined,
)