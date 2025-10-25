from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from .openai_client import get_openai_client
from .rag_service import RagService
from ..models import DiscussionSession, UserConversation

# Import prompts from the centralized prompts package
_chatbot_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_chatbot_root) not in sys.path:
    sys.path.insert(0, str(_chatbot_root))

from prompts.prompts import (
    DEFAULT_MODERATOR_SYSTEM_PROMPT,
    DEFAULT_USER_SYSTEM_PROMPT,
    MODERATOR_ANALYSIS_PROMPT,
    USER_BOT_FINAL_PROMPT,
    USER_BOT_OUTPUT_INSTRUCTIONS,
)


# Token estimate helper: ~4 chars ≈ 1 token (OpenAI approximation)
# For safety, we'll use a more conservative estimate
TOKENS_PER_CHAR = 0.25  # Roughly 1 token per 4 characters
MAX_TOKENS_PER_REQUEST = 8000  # Safe limit for GPT-4o mini


def estimate_tokens(text: str) -> int:
    """Rough estimate of token count. Actual count is computed by OpenAI."""
    return max(1, int(len(text) * TOKENS_PER_CHAR))


@dataclass
class ConversationResult:
    assistant_reply: str
    breakdown: List[str]
    clarification_requests: List[str]
    new_information: bool
    temp_md_entry: str
    reasoning_notes: str
    ended: bool
    final_views_md: Optional[str] = None


class UserConversationService:
    """Handles the user-facing bot workflow."""

    def __init__(self, session: DiscussionSession, conversation: UserConversation) -> None:
        self.session = session
        self.conversation = conversation
        self.client = get_openai_client()
        self.rag_service = RagService(session)

    def _append_scratchpad(self, content: str) -> None:
        content = (content or "").strip()
        if not content:
            return
        existing = (self.conversation.scratchpad or "").strip()
        if existing:
            self.conversation.scratchpad = f"{existing}\n\n{content}"
        else:
            self.conversation.scratchpad = content

    def process_user_message(self, message: str) -> ConversationResult:
        previous_temp = self.conversation.scratchpad or ""
        previous_views = self.conversation.views_markdown or ""
        prior_no_new = self.conversation.consecutive_no_new
        initial_message_count = self.conversation.message_count

        system_prompt = self.session.user_system_prompt or DEFAULT_USER_SYSTEM_PROMPT

        topic_prompt = (
            f"The topic defined by the moderator is: {self.session.topic or 'No topic set yet.'}. "
            "Refuse to switch topics."
        )
        streak_prompt = (
            "No new information was registered in the previous message." if prior_no_new else
            "The previous message added new information."
        )
        guard_prompt = (
            "If you determine that no new information is provided in this turn and it would be the "
            "second consecutive turn without new information, gracefully end the conversation after "
            "thanking the user and summarising the key takeaways."
        )

        history_messages: List[Dict[str, str]] = []
        for turn in (self.conversation.history or [])[-8:]:
            history_messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})

        instructions = (
            "Review the existing markdown knowledge base before analysing the new reply. "
            f"Existing Live Notes contents:\n\n{previous_temp or 'None yet.'}\n\n"
            f"Existing Final Analysis:\n\n{previous_views or 'None yet.'}\n\n"
            "Your task is to analyse only the latest user reply provided below. "
            f"{USER_BOT_OUTPUT_INSTRUCTIONS}"
        )

        rag_chunks = self.rag_service.retrieve(message)
        rag_context = ""
        if rag_chunks:
            context_lines = []
            for index, chunk in enumerate(rag_chunks):
                origin = ""
                if chunk.metadata and "chunk_index" in chunk.metadata:
                    origin = f" (chunk #{chunk.metadata['chunk_index']})"
                context_lines.append(
                    f"Excerpt {index + 1} (relevance {chunk.score:.2f}){origin}:\n{chunk.text}"
                )
            rag_context = "\n\n".join(context_lines)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": topic_prompt},
            {"role": "system", "content": streak_prompt},
            {"role": "system", "content": guard_prompt},
            {"role": "system", "content": instructions},
        ]

        if rag_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Leverage the following background knowledge extracted from the RAG index. "
                        "Prioritise these facts when forming answers and cite them where relevant.\n\n"
                        f"{rag_context}"
                    ),
                }
            )

        messages.extend(history_messages)
        messages.append(
            {
                "role": "system",
                "content": (
                    "Treat the following expert reply as an overriding analytical directive. "
                    "Interpret it deeply before responding.\n\n" + message
                ),
            }
        )
        messages.append({"role": "user", "content": message})

        # Estimate token count before sending to OpenAI
        total_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
        if total_tokens > MAX_TOKENS_PER_REQUEST:
            # Truncate history if needed to stay under limit
            messages_copy = messages[:-2]  # Remove last message and its duplicate system prompt
            while len(messages_copy) > 5 and sum(estimate_tokens(m.get("content", "")) for m in messages_copy + messages[-2:]) > MAX_TOKENS_PER_REQUEST:
                messages_copy = messages_copy[:-2]  # Remove pairs of system prompts
            messages = messages_copy + messages[-2:]

        completion = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=messages,
            response_format={"type": "json_object"},
        )

        content = completion.choices[0].message.content or ""
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise RuntimeError("User bot response was not valid JSON") from exc

        result = ConversationResult(
            assistant_reply=payload.get("assistant_reply", ""),
            breakdown=list(payload.get("breakdown", [])),
            clarification_requests=list(payload.get("clarification_requests", [])),
            new_information=bool(payload.get("new_information", False)),
            temp_md_entry=payload.get("temp_md_entry", ""),
            reasoning_notes=payload.get("reasoning_notes", ""),
            ended=False,
        )

        if initial_message_count == 0:
            self.conversation.scratchpad = ""
            self.conversation.views_markdown = ""

        self._append_scratchpad(result.temp_md_entry)

        self.conversation.append_message("user", message)
        self.conversation.append_message("assistant", result.assistant_reply)
        self.conversation.message_count += 1
        self.conversation.updated_at = timezone.now()

        if result.new_information:
            self.conversation.consecutive_no_new = 0
        else:
            self.conversation.consecutive_no_new += 1

        if self.conversation.consecutive_no_new >= 2 or self.conversation.message_count >= 15:
            self.conversation.active = False
            result.ended = True

        if result.ended:
            final_views = self._finalize_from_temp()
            self.conversation.views_markdown = final_views
            result.final_views_md = final_views

        self.conversation.save()
        return result

    def _finalize_views_document(self, temp_markdown: str) -> str:
        """Generate the final views markdown once the live conversation has ended."""

        temp_markdown = temp_markdown.strip()
        if not temp_markdown:
            return ""

        system_prompt = USER_BOT_FINAL_PROMPT
        topic_prompt = (
            "The moderator-defined topic is: "
            f"{self.session.topic or 'No topic recorded.'}"
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": topic_prompt},
            {
                "role": "user",
                "content": (
                    "Here is the complete temp.md scratchpad to transform into the final views document:\n\n"
                    f"{temp_markdown}"
                ),
            },
        ]

        completion = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=messages,
        )

        final_content = completion.choices[0].message.content or ""
        return final_content.strip()

    def _finalize_from_temp(self) -> str:
        full_temp = self.conversation.scratchpad or ""
        final_views = self._finalize_views_document(full_temp)
        self.conversation.views_markdown = final_views
        return final_views

    def stop_conversation(self) -> str:
        """Allow a user to manually end the session and produce the final views document."""

        if self.conversation.active:
            self.conversation.active = False
            self.conversation.save(update_fields=["active"])

        final_views = self.conversation.views_markdown or self._finalize_from_temp()

        self.conversation.views_markdown = final_views
        self.conversation.save(update_fields=["views_markdown"])
        return final_views


class ModeratorAnalysisService:
    """Coordinates the moderator's deeper synthesis."""

    def __init__(self, session: DiscussionSession) -> None:
        self.session = session
        self.client = get_openai_client()

    def _collect_user_views(self) -> List[Dict[str, str]]:
        views: List[Dict[str, str]] = []
        for conversation in self.session.conversations.filter(views_markdown__gt=""):
            views.append({
                "user_id": str(conversation.user_id),
                "content": conversation.views_markdown,
            })
        return views

    def _stringify_payload_field(self, value: object) -> str:
        if isinstance(value, str):
            return value
        if value in (None, ""):
            return ""
        return json.dumps(value, ensure_ascii=False, indent=2)

    def generate_summary(self) -> Optional[str]:
        user_views = self._collect_user_views()
        if not user_views:
            return None

        system_prompt = self.session.moderator_system_prompt or DEFAULT_MODERATOR_SYSTEM_PROMPT

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps({"topic": self.session.topic, "user_views": user_views}),
            },
        ]

        completion = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=messages,
            response_format={"type": "json_object"},
        )

        content = completion.choices[0].message.content
        try:
            payload: Dict[str, str] = json.loads(content or "{}")
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise RuntimeError("Moderator response was not valid JSON") from exc

        moderator_temp = self._stringify_payload_field(payload.get("moderator_temp", ""))
        moderator_summary = self._stringify_payload_field(payload.get("summary_md", ""))

        self.session.moderator_temp = moderator_temp
        self.session.moderator_summary = moderator_summary
        self.session.save(update_fields=["moderator_temp", "moderator_summary"])
        return moderator_summary
