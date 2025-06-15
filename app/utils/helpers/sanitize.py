"""Helper functions to sanitize user-provided strings for Jinja templates."""

from __future__ import annotations


def escape_braces(value: str) -> str:
    """Replace Jinja delimiters with harmless sequences."""
    return (
        value.replace("{{", "{ {")
        .replace("}}", "} }")
        .replace("{%", "{ %")
        .replace("%}", "% }")
    )


def escape_braces_json(obj):
    """Recursively apply :func:`escape_braces` to all strings in ``obj``."""
    if isinstance(obj, str):
        return escape_braces(obj)
    if isinstance(obj, list):
        return [escape_braces_json(v) for v in obj]
    if isinstance(obj, dict):
        return {k: escape_braces_json(v) for k, v in obj.items()}
    return obj
