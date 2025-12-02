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
    """Represents a full moderator-led discussion workflow (Human-AI deliberation).
    
    Questions are stored in a unified format:
    objective_questions: list of dicts with keys:
        - text: str (the question text)
        - type: str ("grading" or "discussion")
    
    Grading questions: user provides a 1-10 score and a reason. No follow-up.
    Discussion questions: AI-facilitated conversation with up to 3 follow-ups.
    """

    s_id = models.CharField(max_length=64, unique=True)
    # Ordered collection of questions (both grading and discussion) shared by all participants.
    # Each entry is a dict: {"text": "...", "type": "grading"|"discussion"}
    objective_questions = models.JSONField(default=list, blank=True)
    # Follow-up limit for discussion questions (grading questions always have 0)
    question_followup_limit = models.PositiveIntegerField(default=3)
    no_new_information_limit = models.PositiveIntegerField(default=2)
    topic = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, help_text="Detailed description (rendered as markdown for users)")
    user_system_prompt = models.TextField(
        blank=True,
        default=DEFAULT_USER_SYSTEM_PROMPT,
    )
    moderator_system_prompt = models.TextField(
        blank=True,
        default=DEFAULT_MODERATOR_SYSTEM_PROMPT,
    )
    user_instructions = models.TextField(
        blank=True,
        help_text="Optional moderator-provided instructions for participants",
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

    def get_all_questions(self) -> list[dict]:
        """Return the ordered list of all questions with their types.
        
        Returns list of dicts: [{"text": "...", "type": "grading"|"discussion"}, ...]
        """
        questions = []
        for entry in self.objective_questions or []:
            if isinstance(entry, dict):
                text = str(entry.get("text", "")).strip()
                qtype = str(entry.get("type", "discussion")).strip().lower()
                if qtype not in ("grading", "discussion"):
                    qtype = "discussion"
                if text:
                    questions.append({"text": text, "type": qtype})
            elif isinstance(entry, str):
                # Legacy support: plain string becomes a discussion question
                candidate = entry.strip()
                if candidate:
                    questions.append({"text": candidate, "type": "discussion"})
        return questions

    def get_question_sequence(self) -> list[str]:
        """Return the ordered list of question texts (for backward compatibility)."""
        return [q["text"] for q in self.get_all_questions()]

    def get_discussion_questions(self) -> list[dict]:
        """Return only discussion-type questions."""
        return [q for q in self.get_all_questions() if q["type"] == "discussion"]

    def get_grading_questions(self) -> list[dict]:
        """Return only grading-type questions."""
        return [q for q in self.get_all_questions() if q["type"] == "grading"]

    def get_question_count(self) -> int:
        return len(self.get_all_questions())

    def get_question_at(self, index: int) -> dict | None:
        """Return the question dict at the given index, or None if out of bounds."""
        sequence = self.get_all_questions()
        if 0 <= index < len(sequence):
            return sequence[index]
        return None

    def get_question_text_at(self, index: int) -> str:
        """Return just the question text at the given index."""
        q = self.get_question_at(index)
        return q["text"] if q else ""

    def get_question_type_at(self, index: int) -> str:
        """Return the question type at the given index."""
        q = self.get_question_at(index)
        return q["type"] if q else "discussion"

    def get_objective_for_user(self, user_id: int, *, conversation: "UserConversation | None" = None) -> str:
        """Return the active objective question text for the participant."""

        target_conversation = conversation
        if target_conversation is None:
            target_conversation = self.conversations.filter(user_id=user_id).first()
        if target_conversation is not None:
            return self.get_question_text_at(target_conversation.current_question_index)
        return self.get_question_text_at(0)

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
    """Tracks one user's discussion history and state within a session.
    
    The responses field stores all user responses in order, keyed by question index:
    [
        {"question_index": 0, "question_text": "...", "question_type": "grading", 
         "score": 8, "reason": "...", "discussion_history": []},
        {"question_index": 1, "question_text": "...", "question_type": "discussion",
         "score": null, "reason": null, "discussion_history": [{"role": "user", "content": "..."}, ...]},
        ...
    ]
    """

    session = models.ForeignKey(
        DiscussionSession,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    user_id = models.PositiveIntegerField()
    history = models.JSONField(default=list, blank=True)  # Legacy: full conversation history
    # Per-question responses (unified format for grading and discussion)
    responses = models.JSONField(default=list, blank=True)
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

    def get_response_for_question(self, question_index: int) -> dict | None:
        """Get stored response for a specific question index."""
        for resp in self.responses or []:
            if resp.get("question_index") == question_index:
                return resp
        return None

    def set_response_for_question(
        self,
        question_index: int,
        question_text: str,
        question_type: str,
        score: int | None = None,
        reason: str | None = None,
        discussion_history: list | None = None,
    ) -> None:
        """Store or update response for a specific question."""
        responses = list(self.responses or [])
        
        # Find and update existing, or append new
        found = False
        for resp in responses:
            if resp.get("question_index") == question_index:
                resp["question_text"] = question_text
                resp["question_type"] = question_type
                if score is not None:
                    resp["score"] = score
                if reason is not None:
                    resp["reason"] = reason
                if discussion_history is not None:
                    resp["discussion_history"] = discussion_history
                found = True
                break
        
        if not found:
            responses.append({
                "question_index": question_index,
                "question_text": question_text,
                "question_type": question_type,
                "score": score,
                "reason": reason,
                "discussion_history": discussion_history or [],
            })
        
        self.responses = responses

    def get_all_responses(self) -> list[dict]:
        """Get all stored responses sorted by question index."""
        responses = list(self.responses or [])
        return sorted(responses, key=lambda x: x.get("question_index", 0))

    def __str__(self) -> str:
        return f"UserConversation<session={self.session_id}, user={self.user_id}>"


class AIDeliberationSession(models.Model):
    """Represents an AI-only deliberation session (AI-AI debate)."""

    s_id = models.CharField(max_length=64, unique=True)
    topic = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, help_text="Detailed session description")
    # Ordered collection of objective questions for the debate
    objective_questions = models.JSONField(default=list, blank=True)
    # List of personas (AI agent descriptions)
    personas = models.JSONField(default=list, blank=True)
    # Settings
    system_prompt_template = models.TextField(
        blank=True,
        help_text="System prompt template (placeholders: {persona}, {question}, {opinions})",
    )
    user_instructions = models.TextField(
        blank=True,
        help_text="Optional moderator-provided instructions for AI agents",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")

    def __str__(self) -> str:
        return f"AIDeliberationSession<{self.s_id}>"

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

    def get_personas(self) -> list[str]:
        """Return the list of personas for this session."""
        personas = []
        for entry in self.personas or []:
            if isinstance(entry, str):
                candidate = entry.strip()
            else:
                candidate = str(entry).strip()
            if candidate:
                personas.append(candidate)
        return personas

    @classmethod
    def get_active(cls) -> "AIDeliberationSession":
        """Return the active AI session, creating a default if needed."""
        session = cls.objects.filter(is_active=True).order_by("-updated_at").first()
        if session:
            return session
        return cls.objects.create(
            s_id="ai-default",
            topic="Default AI Deliberation",
            objective_questions=[],
            personas=[],
        )

    def activate(self) -> None:
        """Mark this session as the active one."""
        type(self).objects.exclude(pk=self.pk).update(is_active=False)
        if not self.is_active:
            self.is_active = True
            self.save(update_fields=["is_active"])


class AIDebateRun(models.Model):
    """Records a single run of an AI debate (the transcript)."""

    session = models.ForeignKey(
        AIDeliberationSession,
        on_delete=models.CASCADE,
        related_name="debate_runs",
    )
    # Debate transcript: list of turns with {question, persona, opinion, summary}
    transcript = models.JSONField(default=list, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"AIDebateRun<session={self.session_id}, completed={self.completed}>"


class AIDebateSummary(models.Model):
    """Stores the final summary of an AI debate."""

    session = models.OneToOneField(
        AIDeliberationSession,
        on_delete=models.CASCADE,
        related_name="summary",
    )
    topic = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    objective_questions = models.JSONField(default=list, blank=True)
    personas = models.JSONField(default=list, blank=True)
    summary_markdown = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "AI Debate Summaries"

    def __str__(self) -> str:
        return f"AIDebateSummary<session={self.session_id}>"


class GraderSession(models.Model):
    """Represents a grader-style session where participants assign numeric scores to objective questions."""

    s_id = models.CharField(max_length=64, unique=True)
    topic = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, help_text="Detailed session description (rendered as markdown)")
    # Ordered collection of objective questions for the grader
    objective_questions = models.JSONField(default=list, blank=True)
    # Optional knowledge base used for RAG when generating suggestions
    knowledge_base = models.TextField(blank=True)
    rag_chunk_count = models.PositiveIntegerField(default=0)
    rag_last_built_at = models.DateTimeField(null=True, blank=True)
    user_instructions = models.TextField(blank=True, help_text="Optional moderator-provided instructions for graders")
    analysis_markdown = models.TextField(blank=True, help_text="LLM-generated analysis of collected grader feedback")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")

    def __str__(self) -> str:
        return f"GraderSession<{self.s_id}>"

    def get_question_sequence(self) -> list[str]:
        questions = []
        for entry in self.objective_questions or []:
            if isinstance(entry, str):
                candidate = entry.strip()
            else:
                candidate = str(entry).strip()
            if candidate:
                questions.append(candidate)
        return questions

    @classmethod
    def get_active(cls) -> "GraderSession":
        session = cls.objects.filter(is_active=True).order_by("-updated_at").first()
        if session:
            return session
        return cls.objects.create(s_id="grader-default", topic="Default Grader Session", objective_questions=[])

    def activate(self) -> None:
        type(self).objects.exclude(pk=self.pk).update(is_active=False)
        if not self.is_active:
            self.is_active = True
            self.save(update_fields=["is_active"]) 


class GraderResponse(models.Model):
    """Stores one participant's grader responses for a GraderSession.

    - scores: list of integers (1-10) aligned with session objective_questions
    - reasons: list of strings giving a reason for each score
    - additional_comments: optional free-text from the participant
    """

    session = models.ForeignKey(GraderSession, on_delete=models.CASCADE, related_name="responses")
    user_id = models.PositiveIntegerField()
    scores = models.JSONField(default=list, blank=True)
    reasons = models.JSONField(default=list, blank=True)
    additional_comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-submitted_at",)
        constraints = [
            models.UniqueConstraint(fields=("session", "user_id"), name="unique_grader_response_per_user"),
        ]

    def __str__(self) -> str:
        return f"GraderResponse<session={self.session_id}, user={self.user_id}>"


# Note: DiscussionGraderResponse is no longer needed. Responses are now stored 
# inline in UserConversation.responses for unified question handling.

