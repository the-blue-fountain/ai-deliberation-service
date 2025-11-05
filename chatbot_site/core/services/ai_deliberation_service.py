"""Service for running AI-only deliberation sessions."""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from django.conf import settings
from django.db import close_old_connections

from .openai_client import get_openai_client
from ..models import AIDeliberationSession, AIDebateRun

# Token estimate helper
TOKENS_PER_CHAR = 0.25
MAX_TOKENS_PER_REQUEST = 8000


def estimate_tokens(text: str) -> int:
    """Rough estimate of token count."""
    return max(1, int(len(text) * TOKENS_PER_CHAR))


class AIDeliberationService:
    """Orchestrates the AI-only debate workflow."""

    def __init__(self, session: AIDeliberationSession) -> None:
        self.session = session
        self.client = get_openai_client()
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_deliberation(self, blocking: bool = False) -> AIDebateRun:
        """Kick off a deliberation run.

        Args:
            blocking: When True, execute synchronously (useful for tests).
                      When False, the run executes in a background thread and
                      callers should poll the returned run for completion.
        """

        run = AIDebateRun.objects.create(session=self.session)

        if blocking:
            self._execute_and_store(run)
        else:
            thread = threading.Thread(
                target=self._execute_and_store_thread,
                args=(run.pk,),
                daemon=True,
            )
            thread.start()

        return run

    def run_deliberation(self) -> AIDebateRun:
        """Backwards-compatible helper that runs deliberation synchronously."""

        return self.start_deliberation(blocking=True)

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------

    def _execute_and_store_thread(self, run_pk: int) -> None:
        """Worker entry point for the background thread."""

        close_old_connections()
        try:
            run = AIDebateRun.objects.get(pk=run_pk)
        except AIDebateRun.DoesNotExist:  # pragma: no cover - defensive
            self.logger.error("AIDebateRun %s disappeared before execution", run_pk)
            close_old_connections()
            return

        try:
            self._execute_and_store(run)
        finally:
            close_old_connections()

    def _execute_and_store(self, run: AIDebateRun) -> None:
        """Execute the debate and persist transcript + completion flag."""

        try:
            transcript = self._execute_debate()
            run.transcript = transcript
            run.completed = True
            run.save(update_fields=["transcript", "completed", "updated_at"])
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.exception("AI deliberation failed for session %s", self.session.pk)
            run.transcript = [
                {
                    "stage": "error",
                    "persona": "system",
                    "content": f"Deliberation failed: {exc}",
                }
            ]
            run.completed = True
            run.save(update_fields=["transcript", "completed", "updated_at"])

    def _execute_debate(self) -> List[Dict[str, object]]:
        """Run the debate workflow and return the transcript payload."""

        questions = self.session.get_question_sequence()
        personas = self.session.get_personas()

        if not questions or not personas:
            return []

        transcript: List[Dict[str, object]] = []

        for question_idx, question in enumerate(questions):
            initial_opinions: List[Dict[str, str]] = []

            # Round 1: gather each persona's standalone response
            for agent_idx, persona in enumerate(personas):
                response_text = self._get_agent_opinion(
                    persona=persona,
                    question=question,
                    peer_opinions=None,
                    user_instructions=self.session.user_instructions,
                    stage="initial",
                )

                initial_opinion = {"persona": persona, "opinion": response_text}
                initial_opinions.append(initial_opinion)

                transcript.append(
                    {
                        "question_index": question_idx,
                        "question": question,
                        "stage": "initial",
                        "agent_index": agent_idx,
                        "persona": persona,
                        "content": response_text,
                    }
                )

            if len(initial_opinions) < 2:
                # With fewer than two agents there is no critique round
                continue

            # Round 2: each persona critiques their peers' full responses
            for agent_idx, persona in enumerate(personas):
                peer_opinions = [
                    {"persona": op["persona"], "opinion": op["opinion"]}
                    for idx, op in enumerate(initial_opinions)
                    if idx != agent_idx
                ]

                response_text = self._get_agent_opinion(
                    persona=persona,
                    question=question,
                    peer_opinions=peer_opinions,
                    user_instructions=self.session.user_instructions,
                    stage="critique",
                )

                transcript.append(
                    {
                        "question_index": question_idx,
                        "question": question,
                        "stage": "critique",
                        "agent_index": agent_idx,
                        "persona": persona,
                        "content": response_text,
                        "peer_opinions": peer_opinions,
                    }
                )

        return transcript

    def _get_agent_opinion(
        self,
        persona: str,
        question: str,
        peer_opinions: Optional[List[Dict[str, str]]] = None,
        user_instructions: str = "",
        stage: str = "initial",
    ) -> str:
        """Get one agent's opinion on the question given optional peer inputs."""

        system_prompt = (
            f"You are an AI agent whose personality and perspective is described as follows:\n"
            f"{persona}\n\n"
            "You are participating in a structured debate with other AI agents."
        )

        if user_instructions and user_instructions.strip():
            system_prompt += f"\n\nMODERATOR INSTRUCTIONS:\n{user_instructions}"

        user_prompt_lines: List[str] = [f"Objective question: {question}"]

        if peer_opinions:
            user_prompt_lines.append("These are the opinions of your fellow debaters. Do you wish to critique them?")
            for peer in peer_opinions:
                peer_persona = peer.get("persona", "Peer")
                peer_view = peer.get("opinion", "")
                user_prompt_lines.append(f"{peer_persona}: {peer_view}")
            user_prompt_lines.append(
                "Offer your critique. You may agree, disagree, or refine their arguments, but clearly state where you align or diverge."
            )
        else:
            user_prompt_lines.append(
                "Share your detailed perspective on this question before hearing from the other debaters."
            )

        user_prompt = "\n\n".join(line for line in user_prompt_lines if line)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        completion = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=messages,
            temperature=0.7,
        )

        return completion.choices[0].message.content or ""

    def generate_summary(self, run: AIDebateRun) -> Optional[str]:
        """Generate a markdown summary of the debate from its transcript."""

        if not run.transcript:
            return None

        transcript_text = self._format_transcript_for_summary(run.transcript)

        system_prompt = (
            f"You are synthesizing insights from an AI-driven deliberation session.\n"
            f"Topic: {self.session.topic}\n\n"
            f"Session description: {self.session.description or 'None provided'}\n\n"
            "Generate a comprehensive markdown summary that captures:\n"
            "- Key themes and areas of agreement\n"
            "- Major points of divergence\n"
            "- Notable arguments or perspectives\n"
            "- Synthesis of insights"
        )

        user_prompt = (
            f"Here is the debate transcript:\n\n{transcript_text}\n\n"
            "Please generate a well-structured markdown summary."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        completion = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=messages,
            temperature=0.6,
        )

        return completion.choices[0].message.content or ""

    def _format_transcript_for_summary(self, transcript: List[Dict]) -> str:
        """Format the transcript into readable text for summary generation."""

        lines: List[str] = []
        current_question = None
        current_stage = None
        current_round = None  # Backwards compatibility with older transcripts

        for turn in transcript:
            question = turn.get("question", "")
            persona = turn.get("persona", "")
            stage = turn.get("stage")
            opinion = turn.get("content") or turn.get("opinion", "")

            if question != current_question:
                current_question = question
                current_stage = None
                current_round = None
                lines.append(f"\n## Question: {question}\n")

            if stage:
                if stage != current_stage:
                    current_stage = stage
                    stage_heading = "Initial Responses" if stage == "initial" else "Critique Round"
                    lines.append(f"\n### {stage_heading}\n")
            else:
                round_num = turn.get("round")
                if round_num is not None and round_num != current_round:
                    current_round = round_num
                    lines.append(f"\n### Round {round_num}\n")

            lines.append(f"**Agent ({persona}):**")
            lines.append(opinion)
            lines.append("")

        return "\n".join(lines)


