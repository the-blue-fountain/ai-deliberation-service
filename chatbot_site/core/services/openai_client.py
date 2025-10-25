from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from openai import OpenAI


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Return a cached OpenAI client configured for the project."""

    return OpenAI(api_key=settings.OPENAI_API_KEY)
