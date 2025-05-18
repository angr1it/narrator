from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

TEMPLATE_DIR = "templates/cypher"


env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=False,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
