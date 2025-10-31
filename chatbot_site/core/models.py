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
    # Ordered collection of objective questions shared by all participants.
    objective_questions = models.JSONField(default=list, blank=True)
    question_followup_limit = models.PositiveIntegerField(default=3)
    no_new_information_limit = models.PositiveIntegerField(default=2)
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

    def get_question_sequence(self) -> list[str]:
        """Return the ordered list of objective questions for this session."""

        questions = []
        for entry in self.objective_questions or []:
            if isinstance(entry, str):
                candidate = entry.strip()
            else:
                candidate = str(entry).strip()
            if candidate:
                questions.append(candidate)
        return questions

    def get_question_count(self) -> int:
        return len(self.get_question_sequence())

    def get_question_at(self, index: int) -> str:
        sequence = self.get_question_sequence()
        if 0 <= index < len(sequence):
            return sequence[index]
        return ""

    def get_objective_for_user(self, user_id: int, *, conversation: "UserConversation | None" = None) -> str:
        """Return the active objective question for the participant.

        If a conversation instance is supplied (or found via user_id), the current
        question index will be used. Otherwise, the first question (if any) is
        returned. Maintains API compatibility with legacy callers.
        """

        target_conversation = conversation
        if target_conversation is None:
            target_conversation = self.conversations.filter(user_id=user_id).first()
        if target_conversation is not None:
            return self.get_question_at(target_conversation.current_question_index)
        return self.get_question_at(0)

    @classmethod
    def get_active(cls) -> "DiscussionSession":
        """Return the active session, creating a default if needed."""

        session = cls.objects.active().first()
        if session:
            return session
        return cls.objects.create(
            s_id="default",
            topic="Default Discussion",
            objective_questions=[],
            question_followup_limit=3,
            no_new_information_limit=2,
        )


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
    current_question_index = models.PositiveIntegerField(default=0)
    question_followups = models.PositiveIntegerField(default=0)
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
