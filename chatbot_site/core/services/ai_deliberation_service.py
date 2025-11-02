"""Service for running AI-only deliberation sessions."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from .openai_client import get_openai_client
from ..models import AIDeliberationSession, AIDebateRun, AIDebateSummary

# Token estimate helper
TOKENS_PER_CHAR = 0.25
MAX_TOKENS_PER_REQUEST = 8000


def estimate_tokens(text: str) -> int:
    """Rough estimate of token count."""
    return max(1, int(len(text) * TOKENS_PER_CHAR))


@dataclass
class AgentOpinion:
    """Represents one agent's opinion on a question."""

    persona: str
    opinion: str
    summary: str  # Terse summary for sharing with other agents


class AIDeliberationService:
    """Orchestrates the AI-only debate workflow."""

    def __init__(self, session: AIDeliberationSession) -> None:
        self.session = session
        self.client = get_openai_client()

    def run_deliberation(self) -> AIDebateRun:
        """Run a two-round deliberation for all questions and all agents.

        Round 1: Each agent states opinion sequentially (A→B→C)
        Round 2: Each agent responds to previous agents in rotating order (B→C→A, then C→A→B, then A→B→C)

        Returns the populated AIDebateRun transcript with both rounds.
        """
        # Create the run record
        run = AIDebateRun.objects.create(session=self.session)

        questions = self.session.get_question_sequence()
        personas = self.session.get_personas()

        if not questions or not personas:
            run.completed = True
            run.save()
            return run

        transcript: List[Dict] = []
        num_agents = len(personas)

        # For each question
        for question_idx, question in enumerate(questions):
            # ===== ROUND 1: Sequential opinions =====
            # Store round 1 opinions indexed by agent_idx
            round1_opinions: Dict[int, AgentOpinion] = {}
            opinions_so_far: List[AgentOpinion] = []

            for agent_idx, persona in enumerate(personas):
                # Get this agent's opinion (hearing all previous agents' summaries)
                opinion = self._get_agent_opinion(
                    persona=persona,
                    question=question,
                    prior_opinions=opinions_so_far,
                    user_instructions=self.session.user_instructions,
                    round_number=1,
                )

                opinions_so_far.append(opinion)
                round1_opinions[agent_idx] = opinion

                # Record in transcript
                transcript.append({
                    "question_index": question_idx,
                    "question": question,
                    "round": 1,
                    "agent_index": agent_idx,
                    "persona": persona,
                    "opinion": opinion.opinion,
                    "terse_summary": opinion.summary,
                })

            # ===== ROUND 2: Rotating context =====
            # Each agent sees the opinions of the other two in a rotated order
            # If A, B, C: A sees [B, C], B sees [C, A], C sees [A, B]
            round2_opinions: Dict[int, AgentOpinion] = {}

            for starting_agent_idx in range(num_agents):
                # Build the rotating sequence: start from the agent after this one
                rotating_sequence = [
                    (starting_agent_idx + i) % num_agents
                    for i in range(1, num_agents)
                ]
                
                # Get opinions in rotation order (excluding this agent)
                opinions_to_share: List[AgentOpinion] = [
                    round1_opinions[agent_idx]
                    for agent_idx in rotating_sequence
                ]

                agent_persona = personas[starting_agent_idx]
                
                # Get this agent's second opinion
                opinion = self._get_agent_opinion(
                    persona=agent_persona,
                    question=question,
                    prior_opinions=opinions_to_share,
                    user_instructions=self.session.user_instructions,
                    round_number=2,
                )

                round2_opinions[starting_agent_idx] = opinion

                # Record in transcript
                transcript.append({
                    "question_index": question_idx,
                    "question": question,
                    "round": 2,
                    "agent_index": starting_agent_idx,
                    "persona": agent_persona,
                    "opinion": opinion.opinion,
                    "terse_summary": opinion.summary,
                })

        run.transcript = transcript
        run.completed = True
        run.save()
        return run

    def _get_agent_opinion(
        self,
        persona: str,
        question: str,
        prior_opinions: List[AgentOpinion],
        user_instructions: str = "",
        round_number: int = 1,
    ) -> AgentOpinion:
        """Get one agent's opinion on the question given prior opinions.
        
        Args:
            persona: Description of the agent's perspective
            question: The objective question to answer
            prior_opinions: List of AgentOpinion from previous agents
            user_instructions: Optional moderator-provided instructions
            round_number: Which round of deliberation (1 or 2)
        """

        # Build the prior opinions context
        opinions_text = ""
        if prior_opinions:
            lines = []
            for idx, prior in enumerate(prior_opinions):
                lines.append(f"Agent {idx + 1} ({prior.persona}): {prior.summary}")
            opinions_text = "\n".join(lines)

        # Build the system prompt
        system_prompt = (
            f"You are an AI agent whose personality and perspective is described as follows:\n"
            f"{persona}\n\n"
            f"You are participating in a structured debate with other AI agents."
        )

        # Add user instructions if provided
        if user_instructions and user_instructions.strip():
            system_prompt += f"\n\nMODERATOR INSTRUCTIONS:\n{user_instructions}"

        # Build the user prompt
        round_context = f" (Round {round_number} of deliberation)" if round_number > 1 else ""
        user_prompt = (
            f"Objective question{round_context}: {question}\n\n"
        )

        if opinions_text:
            user_prompt += (
                f"Opinions shared by other agents:\n"
                f"{opinions_text}\n\n"
            )

        user_prompt += (
            f"Please state your opinion on this question in clear language. "
            f"You may agree, disagree, or introduce new points. "
            f"Be thoughtful and substantive."
        )

        # Call OpenAI
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        completion = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=messages,
            temperature=0.7,
        )

        opinion_text = completion.choices[0].message.content or ""

        # Generate a terse summary (for sharing with next agents)
        summary = self._generate_terse_summary(
            persona=persona,
            opinion=opinion_text,
        )

        return AgentOpinion(
            persona=persona,
            opinion=opinion_text,
            summary=summary,
        )

    def _generate_terse_summary(self, persona: str, opinion: str) -> str:
        """Generate a terse summary of an agent's opinion for sharing."""

        if not opinion:
            return ""

        # Truncate opinion if too long
        truncated_opinion = opinion if len(opinion) <= 500 else opinion[:500] + "..."

        system_prompt = (
            f"You are summarizing the opinion of an AI agent with this persona:\n"
            f"{persona}\n\n"
            f"Create a very terse (2-3 sentences) summary of their position."
        )

        user_prompt = (
            f"Agent's full opinion:\n{truncated_opinion}\n\n"
            f"Provide a terse summary (2-3 sentences max)."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        completion = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=messages,
            temperature=0.5,
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
            f"Generate a comprehensive markdown summary that captures:\n"
            f"- Key themes and areas of agreement\n"
            f"- Major points of divergence\n"
            f"- Notable arguments or perspectives\n"
            f"- Synthesis of insights"
        )

        user_prompt = (
            f"Here is the debate transcript:\n\n{transcript_text}\n\n"
            f"Please generate a well-structured markdown summary."
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

        lines = []
        current_question = None
        current_round = None

        for turn in transcript:
            question = turn.get("question", "")
            round_num = turn.get("round", 1)
            persona = turn.get("persona", "")
            opinion = turn.get("opinion", "")

            if question != current_question:
                current_question = question
                current_round = None
                lines.append(f"\n## Question: {question}\n")

            if round_num != current_round:
                current_round = round_num
                lines.append(f"\n### Round {round_num}\n")

            lines.append(f"**Agent ({persona}):**")
            lines.append(opinion)
            lines.append("")

        return "\n".join(lines)

