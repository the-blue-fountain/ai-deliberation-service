from __future__ import annotations

from django.db import models

# Import prompts from the centralized prompts package
import sys
from pathlib import Path

# Add parent directory to path to import prompts package
_chatbot_root = Path(__file__).resolve().parent.parent.parent
if str(_chatbot_root) not in sys.path:
    sys.path.insert(0, str(_chatbot_root))

from prompts.prompts import (
    DEFAULT_MODERATOR_SYSTEM_PROMPT,
    DEFAULT_USER_SYSTEM_PROMPT,
)


class DiscussionSessionQuerySet(models.QuerySet):
    def active(self) -> "models.QuerySet[DiscussionSession]":
        return self.filter(is_active=True).order_by("-updated_at")


class DiscussionSession(models.Model):
    """Represents a full moderator-led discussion workflow."""

    s_id = models.CharField(max_length=64, unique=True)
    # A single objective question that will be given to all participants.
    # The system no longer asks moderators to provide a number of users.
    objective_question = models.TextField(blank=True)
    topic = models.CharField(max_length=255, blank=True)
    user_system_prompt = models.TextField(
        blank=True,
        default=DEFAULT_USER_SYSTEM_PROMPT,
    )
    moderator_system_prompt = models.TextField(
        blank=True,
        default=DEFAULT_MODERATOR_SYSTEM_PROMPT,
    )
    knowledge_base = models.TextField(blank=True)
    rag_chunk_count = models.PositiveIntegerField(default=0)
    rag_last_built_at = models.DateTimeField(null=True, blank=True)
    moderator_temp = models.TextField(blank=True)
    moderator_summary = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DiscussionSessionQuerySet.as_manager()

    class Meta:
        ordering = ("-updated_at", "-id")

    def __str__(self) -> str:
        return f"DiscussionSession<{self.s_id}>"

    def activate(self) -> None:
        """Mark this session as the active one for incoming users."""

        type(self).objects.exclude(pk=self.pk).update(is_active=False)
        if not self.is_active:
            self.is_active = True
            self.save(update_fields=["is_active"])

    def get_objective_for_user(self, user_id: int) -> str:
        """Return the current objective question for participants.

        The platform now uses a single objective question shared by all users.
        The user_id is ignored but kept for API compatibility.
        """
        return (self.objective_question or "").strip()

    @classmethod
    def get_active(cls) -> "DiscussionSession":
        """Return the active session, creating a default if needed."""

        session = cls.objects.active().first()
        if session:
            return session
        return cls.objects.create(s_id="default")


class UserConversation(models.Model):
    """Tracks one user's discussion history and state within a session."""

    session = models.ForeignKey(
        DiscussionSession,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    user_id = models.PositiveIntegerField()
    history = models.JSONField(default=list, blank=True)
    scratchpad = models.TextField(blank=True)
    views_markdown = models.TextField(blank=True)
    message_count = models.PositiveIntegerField(default=0)
    consecutive_no_new = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("session_id", "user_id")
        constraints = [
            models.UniqueConstraint(
                fields=("session", "user_id"),
                name="unique_user_per_session",
            ),
        ]

    def append_message(self, role: str, content: str) -> None:
        """Append a chat turn to the JSON history."""

        payload = list(self.history or [])
        payload.append({"role": role, "content": content})
        self.history = payload

    def __str__(self) -> str:
        return f"UserConversation<session={self.session_id}, user={self.user_id}>"
