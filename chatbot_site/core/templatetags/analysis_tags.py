import json
from django import template
import markdown

register = template.Library()


@register.filter
def parse_json(value):
    """Parse JSON string and return the object."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary."""
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key, [])


@register.filter
def render_markdown(value):
    """Render markdown string to HTML."""
    if not value:
        return ""
    try:
        return markdown.markdown(value, safe_mode=False)
    except Exception:
        # Fallback to plain text if rendering fails
        return value

