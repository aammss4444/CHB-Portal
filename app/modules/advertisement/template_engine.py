import logging
import re
from typing import Any, Dict


logger = logging.getLogger(__name__)
PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class TemplateRenderError(Exception):
    def __init__(self, message: str, missing_keys: list[str] | None = None):
        super().__init__(message)
        self.missing_keys = missing_keys or []


def render_advertisement(template_body: str, context: Dict[str, Any]) -> str:
    """Render an advertisement template by replacing {{key}} placeholders from context."""
    render_context = dict(context)
    render_context.setdefault("designation", "Assistant Professor")
    render_context.setdefault("qualification", "ME / M.Tech in relevant field")

    replaced_keys: set[str] = set()

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in render_context:
            return match.group(0)
        replaced_keys.add(key)
        return str(render_context[key])

    rendered = PLACEHOLDER_PATTERN.sub(_replace, template_body)
    missing = sorted(set(PLACEHOLDER_PATTERN.findall(rendered)))

    logger.info("Advertisement template placeholders replaced: %s", sorted(replaced_keys))

    if missing:
        raise TemplateRenderError(
            f"Missing values for placeholders: {', '.join(missing)}",
            missing_keys=missing,
        )

    return rendered
