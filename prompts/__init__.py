"""
Centralized prompt management for DiscussChat.

This module contains all system prompts and instructions used by the chatbot system,
organized by role (user bot and moderator bot) with detailed documentation for each.
"""

# Re-export from prompts module
__all__ = [
    "DEFAULT_USER_SYSTEM_PROMPT",
    "DEFAULT_MODERATOR_SYSTEM_PROMPT",
    "USER_BOT_BASE_PROMPT",
    "USER_BOT_REASONING_PROMPT",
    "USER_BOT_OUTPUT_INSTRUCTIONS",
    "USER_BOT_FINAL_PROMPT",
    "MODERATOR_ANALYSIS_PROMPT",
]
