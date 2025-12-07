from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import (
    DiscussionSessionForm,
    ParticipantIdForm,
    SessionSelectionForm,
    UserMessageForm,
)
from .models import DiscussionSession, UserConversation
from .services.conversation_service import (
    ModeratorAnalysisService,
    UserConversationService,
)
from .services.rag_service import RagService
from .services.openai_client import get_openai_client
from django.conf import settings
import csv
import io


@require_http_methods(["POST"])
def create_new_session_api(request: HttpRequest) -> JsonResponse:
    """API endpoint for creating a new session via modal form."""
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    
    s_id = data.get("s_id", "").strip()
    topic = data.get("topic", "").strip()
    
    # Validation
    if not s_id:
        return JsonResponse({"success": False, "error": "Session ID is required"})
    
    if not topic:
        return JsonResponse({"success": False, "error": "Topic is required"})
    
    # Check for duplicate session ID
    if DiscussionSession.objects.filter(s_id=s_id).exists():
        return JsonResponse({"success": False, "error": f"Session ID '{s_id}' already exists"})
    
    try:
        # Deactivate all existing sessions
        DiscussionSession.objects.update(is_active=False)
        
        # Create new session
        new_session = DiscussionSession.objects.create(
            s_id=s_id,
            topic=topic,
            is_active=True,
        )
        
        return JsonResponse({
            "success": True,
            "session_id": new_session.pk,
            "message": f"Session '{s_id}' created successfully",
        })
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)})


@require_http_methods(["POST"])
def generate_questions_api(request: HttpRequest) -> JsonResponse:
    """Generate 4 candidate objective questions for a given topic using the LLM.

    Expects JSON body {"topic": "..."} and returns {"success": True, "questions": [...]}.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    topic = (data.get("topic") or "").strip()
    if not topic:
        return JsonResponse({"success": False, "error": "Topic is required"}, status=400)

    question_type_raw = (data.get("question_type") or "discussion").lower()
    question_type = question_type_raw.strip()
    is_grader_mode = question_type in {"grader", "grading", "score", "scoring"}

    try:
        session_obj: Optional[DiscussionSession] = None
        session_id_value = data.get("session_id")
        if session_id_value:
            try:
                session_obj = DiscussionSession.objects.get(pk=int(session_id_value))
            except (ValueError, TypeError, DiscussionSession.DoesNotExist):
                session_obj = None

        knowledge_base = (data.get("knowledge_base") or "").strip()
        existing_questions_raw = data.get("current_questions") or []
        if not isinstance(existing_questions_raw, list):
            existing_questions_raw = []
        existing_questions = [str(item).strip() for item in existing_questions_raw if str(item).strip()]

        rag_context_chunks: list[str] = []
        if session_obj is not None:
            try:
                rag_snippets = RagService(session_obj).retrieve(topic, top_k=4)
            except Exception:
                rag_snippets = []
            for chunk in rag_snippets:
                text = (chunk.text or "").strip()
                if not text:
                    continue
                if len(text) > 400:
                    text = text[:400].rstrip() + "..."
                rag_context_chunks.append(f"- {text}")

        if not rag_context_chunks and knowledge_base:
            snippet = knowledge_base.strip()
            if len(snippet) > 1500:
                snippet = snippet[:1500].rstrip() + "\n... (truncated)"
            rag_context_chunks.append(snippet)

        client = get_openai_client()
        if is_grader_mode:
            system = (
                "You are a helpful assistant that drafts objective grading prompts. "
                "Given a topic and optional background excerpts, produce exactly four concise prompts that ask participants to assign a score from 1 (poor) to 10 (excellent) and provide a short explanation. "
                "Avoid reusing any prompts that the moderator already selected. "
                "Each prompt must clearly describe what the grader is evaluating while remaining neutral and factual. "
                "Return ONLY a JSON object with a 'questions' key containing an array of 4 prompt strings. "
                "Example format: {\"questions\": [\"Rate how clearly the participant explained...\", ...]}"
            )
        else:
            system = (
                "You are a helpful assistant that creates short, objective, neutral discussion questions. "
                "Given a topic and optional background excerpts, produce exactly four concise objective questions suitable for asking participants. "
                "Avoid reusing any questions that the moderator already selected. "
                "Return ONLY a JSON object with a 'questions' key containing an array of 4 question strings. "
                "Example format: {\"questions\": [\"question 1\", \"question 2\", \"question 3\", \"question 4\"]}"
            )
        user_sections = [f"Topic: {topic}"]
        if existing_questions:
            existing_block = "\n".join(f"- {question}" for question in existing_questions)
            user_sections.append("Existing questions to avoid repeating:\n" + existing_block)
        if rag_context_chunks:
            user_sections.append("Relevant background excerpts:\n" + "\n".join(rag_context_chunks))
        if is_grader_mode:
            user_sections.append(
                "Generate 4 grading prompts. Each prompt should direct the grader to score the participant's performance on a 1-10 scale and explain their reasoning."
            )
        else:
            user_sections.append("Generate 4 short objective questions.")
        user = "\n\n".join(user_sections)
        completion = client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content or ""
        try:
            response_data = json.loads(content)
            questions = response_data.get("questions", [])
            if not isinstance(questions, list):
                questions = []
            # Ensure we have exactly 4 questions and clean them
            questions = [str(q).strip() for q in questions[:4] if q]
        except Exception as e:
            # Fallback: try to extract lines and return up to 4 short lines
            # Remove common JSON artifacts and clean up
            cleaned = content.replace('[', '').replace(']', '').replace('{', '').replace('}', '')
            cleaned = cleaned.replace('"questions":', '').replace('"', '')
            lines = [l.strip('-, ').strip() for l in cleaned.splitlines() if l.strip() and len(l.strip()) > 10]
            questions = [q for q in lines[:4] if q]

        return JsonResponse({"success": True, "questions": questions})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


def entry_point(request: HttpRequest) -> HttpResponse:
    session = DiscussionSession.get_active()
    if request.method == "POST":
        form = ParticipantIdForm(request.POST)
        if form.is_valid():
            participant_id = form.cleaned_data["participant_id"]
            if participant_id == 0:
                return redirect("moderator_dashboard")
            # Go directly to the unified conversation view
            return redirect("user_conversation", user_id=participant_id)
    else:
        form = ParticipantIdForm()

    return render(
        request,
        "core/entry.html",
        {
            "form": form,
            "active_session": session,
        },
    )


def moderator_dashboard(request: HttpRequest) -> HttpResponse:
    sessions = DiscussionSession.objects.all().order_by("-updated_at")
    selected_session: Optional[DiscussionSession] = None

    # Check for session_id in query parameters (from API redirect)
    query_session_id = request.GET.get("session_id")
    if query_session_id:
        try:
            selected_session = sessions.filter(pk=int(query_session_id)).first()
            if selected_session:
                request.session["moderator_selected_session_id"] = int(query_session_id)
        except (TypeError, ValueError):
            pass

    # Fall back to session-stored selection or active session
    if selected_session is None:
        selected_session_id = request.session.get("moderator_selected_session_id")
        if selected_session_id:
            selected_session = sessions.filter(pk=selected_session_id).first()
    
    if selected_session is None:
        selected_session = sessions.filter(is_active=True).order_by("-updated_at").first()

    session_form: DiscussionSessionForm

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "load_session":
            target_id = request.POST.get("session_id")
            if target_id:
                try:
                    request.session["moderator_selected_session_id"] = int(target_id)
                except (TypeError, ValueError):
                    messages.error(request, "Unable to load the requested session.")
                else:
                    return redirect("moderator_dashboard")
            else:
                request.session.pop("moderator_selected_session_id", None)
                return redirect("moderator_dashboard")

        if action in {"save_session", "create_session"}:
            instance = selected_session if (action == "save_session" and selected_session) else None
            session_form = DiscussionSessionForm(request.POST, instance=instance)
            if session_form.is_valid():
                new_session = session_form.save(commit=False)
                if not new_session.pk:
                    new_session.is_active = False
                new_session.save()
                request.session["moderator_selected_session_id"] = new_session.pk
                messages.success(request, "Session saved.")
                return redirect("moderator_dashboard")
        elif action == "activate_session":
            if selected_session is None:
                messages.error(request, "Select a session before activating it.")
            else:
                selected_session.activate()
                request.session["moderator_selected_session_id"] = selected_session.pk
                messages.success(request, f"Session {selected_session.s_id} is now active.")
                return redirect("moderator_dashboard")
        elif action == "run_rag":
            if selected_session is None:
                messages.error(request, "Save or select a session before rebuilding the index.")
            else:
                # Support optional file upload (.txt or .csv) or inline knowledge_base text
                raw_text = None
                uploaded = request.FILES.get('knowledge_file')
                if uploaded is not None:
                    try:
                        content = uploaded.read()
                        try:
                            text = content.decode('utf-8')
                        except Exception:
                            text = content.decode('latin-1')
                        name = (uploaded.name or '').lower()
                        if name.endswith('.csv'):
                            # Parse CSV into human-readable lines
                            reader = csv.reader(io.StringIO(text))
                            rows = [', '.join([cell for cell in row]) for row in reader]
                            raw_text = '\n'.join(rows)
                        else:
                            raw_text = text
                    except Exception as exc:  # pragma: no cover - defensive
                        messages.error(request, f"Failed to read uploaded file: {exc}")
                        return redirect("moderator_dashboard")
                else:
                    # Use posted knowledge_base if provided, otherwise fall back to session field
                    raw_text = request.POST.get('knowledge_base') or None

                try:
                    chunk_count = RagService(selected_session).build_index(raw_text=raw_text)
                except Exception as exc:  # pragma: no cover - defensive
                    messages.error(request, f"Failed to rebuild the RAG index: {exc}")
                else:
                    if chunk_count == 0:
                        messages.warning(
                            request,
                            "RAG index is empty. Add knowledge base content before rebuilding.",
                        )
                    else:
                        messages.success(
                            request,
                            f"RAG index rebuilt with {chunk_count} knowledge snippets.",
                        )
                return redirect("moderator_dashboard")
        elif action == "analyze":
            if selected_session is None:
                messages.error(request, "Select a session before running the analysis.")
            else:
                analyzer = ModeratorAnalysisService(selected_session)
                summary = analyzer.generate_summary()
                if summary is None:
                    messages.info(request, "No user view documents found yet.")
                else:
                    messages.success(request, "Generated moderator summary.")
                return redirect("moderator_dashboard")
    else:
        session_form = DiscussionSessionForm(instance=selected_session)

    if request.method == "POST" and "session_form" not in locals():
        session_form = DiscussionSessionForm(instance=selected_session)

    selection_initial = {
        "session_id": str(selected_session.pk) if selected_session else "",
    }
    selection_form = SessionSelectionForm(
        request.POST if request.method == "POST" else None,
        sessions=sessions,
        initial=selection_initial,
    )

    available_views = []
    if selected_session is not None:
        for conversation in selected_session.conversations.order_by("user_id"):
            available_views.append(
                {
                    "user_id": conversation.user_id,
                    "message_count": conversation.message_count,
                    "active": conversation.active,
                    "has_views": bool(conversation.views_markdown),
                }
            )

    context: Dict[str, Any] = {
        "selection_form": selection_form,
        "session_form": session_form,
        "selected_session": selected_session,
        "sessions": sessions,
        "available_views": available_views,
    }
    return render(request, "core/moderator_dashboard.html", context)


def user_conversation(request: HttpRequest, user_id: int) -> HttpResponse:
    """Unified participant view handling both grading and discussion questions inline."""
    session = DiscussionSession.get_active()
    conversation, _ = UserConversation.objects.get_or_create(session=session, user_id=user_id)

    all_questions = session.get_all_questions() if session else []
    total_questions = len(all_questions)
    current_index = conversation.current_question_index

    # Check if we've completed all questions
    if current_index >= total_questions:
        conversation.active = False
        conversation.save(update_fields=["active"])

    current_question = session.get_question_at(current_index) if session and current_index < total_questions else None
    current_question_text = current_question["text"] if current_question else ""
    current_question_type = current_question["type"] if current_question else "discussion"

    temp_snapshot = conversation.scratchpad or ""
    views_snapshot = conversation.views_markdown or ""
    result_payload: Optional[Dict[str, Any]] = None

    if request.method == "POST":
        action = request.POST.get("action", "send")

        if action == "stop":
            # Manual stop
            service = UserConversationService(session, conversation)
            try:
                final_views = service.stop_conversation()
            except Exception as exc:
                messages.error(request, f"Unable to stop the conversation: {exc}")
            else:
                messages.info(request, "Conversation stopped. Final views document generated.")
                views_snapshot = final_views
                conversation.refresh_from_db()
            temp_snapshot = conversation.scratchpad

        elif action == "submit_grading" and current_question_type == "grading":
            # Handle grading question submission
            score_raw = request.POST.get("score", "")
            reason = request.POST.get("reason", "").strip()

            try:
                score = int(score_raw)
                if not (1 <= score <= 10):
                    raise ValueError("Score out of range")
            except (ValueError, TypeError):
                messages.error(request, "Please provide a valid score between 1 and 10.")
            else:
                if not reason:
                    messages.error(request, "Please provide a reason for your score.")
                else:
                    # Store the grading response
                    conversation.set_response_for_question(
                        question_index=current_index,
                        question_text=current_question_text,
                        question_type="grading",
                        score=score,
                        reason=reason,
                    )

                    # Move to next question (grading questions have no follow-up)
                    conversation.current_question_index = current_index + 1
                    # IMPORTANT: Reset follow-up counters for the new question
                    conversation.question_followups = 0
                    conversation.consecutive_no_new = 0
                    # Clear the conversation history for the new question
                    conversation.history = []

                    # Check if that was the last question
                    if conversation.current_question_index >= total_questions:
                        conversation.active = False
                        # Generate final analysis
                        service = UserConversationService(session, conversation)
                        final_views = service._finalize_from_temp()
                        views_snapshot = final_views
                        messages.info(request, "All questions completed. Thank you for your participation.")
                    else:
                        messages.success(request, "Response recorded. Moving to next question.")

                    conversation.save()
                    return redirect("user_conversation", user_id=user_id)

        elif action == "send" and current_question_type == "discussion":
            # Handle discussion question with AI conversation
            form = UserMessageForm(request.POST)
            if not session.topic:
                messages.error(request, "Cannot start until the moderator shares a topic.")
            elif not conversation.active:
                messages.info(request, "This conversation has already concluded.")
            elif form.is_valid():
                message = form.cleaned_data["message"]
                service = UserConversationService(session, conversation)
                try:
                    result = service.process_user_message(message)
                except Exception as exc:
                    messages.error(request, f"The user bot encountered an error: {exc}")
                else:
                    result_payload = {
                        "assistant_reply": result.assistant_reply,
                        "breakdown": result.breakdown,
                        "clarification_requests": result.clarification_requests,
                        "new_information": result.new_information,
                        "reasoning_notes": result.reasoning_notes,
                        "ended": result.ended,
                        "final_views_md": result.final_views_md,
                        "end_reason": result.end_reason,
                    }
                    temp_snapshot = conversation.scratchpad
                    if result.final_views_md is not None:
                        views_snapshot = result.final_views_md

                    if result.ended:
                        end_reason = result.end_reason or ""
                        if end_reason == "no_new_limit":
                            messages.info(
                                request,
                                "Moving to next question after reaching the limit for consecutive responses without new information.",
                            )
                        elif end_reason == "followup_limit":
                            messages.info(
                                request,
                                "Moving to next question after reaching the follow-up limit.",
                            )
                        elif end_reason == "all_complete":
                            messages.info(request, "All questions completed. Thank you for your participation.")
                        else:
                            messages.info(request, "Conversation closed.")
            else:
                messages.error(request, "Please enter a response before submitting.")

    # Refresh state after potential changes
    conversation.refresh_from_db()
    current_index = conversation.current_question_index
    current_question = session.get_question_at(current_index) if session and current_index < total_questions else None
    current_question_text = current_question["text"] if current_question else ""
    current_question_type = current_question["type"] if current_question else "discussion"

    # For discussion questions, get the next question preview
    next_question = None
    if conversation.active and current_index + 1 < total_questions:
        next_question = session.get_question_at(current_index + 1)

    # Get follow-up info (only relevant for discussion questions)
    followup_limit = session.question_followup_limit if session else 3
    followups_used = conversation.question_followups if current_question_type == "discussion" else 0
    followups_remaining = max(followup_limit - followups_used, 0) if current_question_type == "discussion" else 0

    no_new_limit = session.no_new_information_limit if session else 2
    no_new_streak = conversation.consecutive_no_new if current_question_type == "discussion" else 0
    no_new_remaining = max(no_new_limit - no_new_streak, 0) if current_question_type == "discussion" else 0

    # Get existing grading response for current question (for pre-fill)
    existing_grading = conversation.get_response_for_question(current_index) if current_question_type == "grading" else None

    # Get all responses for display
    all_responses = conversation.get_all_responses()

    context = {
        "session": session,
        "conversation": conversation,
        "form": UserMessageForm(),
        "history": conversation.history or [],
        "result": result_payload,
        "temp_snapshot": temp_snapshot,
        "views_snapshot": views_snapshot,
        "topic": session.topic if session else "",
        "question": current_question_text,
        "question_type": current_question_type,
        "question_data": current_question,
        "all_questions": all_questions,
        "question_total": total_questions,
        "question_position": min(current_index + 1, total_questions) if current_question else total_questions,
        "question_next": next_question,
        "question_followup_limit": followup_limit,
        "question_followups_used": followups_used,
        "question_followups_remaining": followups_remaining,
        "no_new_information_limit": no_new_limit,
        "no_new_information_remaining": no_new_remaining,
        "existing_grading": existing_grading,
        "all_responses": all_responses,
    }
    return render(request, "core/user_conversation.html", context)


# ============================================================================
# AI-AI DELIBERATION VIEWS
# ============================================================================


def system_choice(request: HttpRequest) -> HttpResponse:
    """Entry point: ask user to choose AI-Human or AI-AI deliberation."""
    if request.method == "POST":
        choice = request.POST.get("choice", "").strip()
        if choice == "human":
            return redirect("entry")
        elif choice == "ai":
            return redirect("ai_entry")
        elif choice == "grader":
            return redirect("grader_entry")
    return render(request, "core/system_choice.html")


def ai_entry_point(request: HttpRequest) -> HttpResponse:
    """Entry point for AI-only deliberation (moderator access)."""
    session = _get_or_create_default_ai_session()
    return render(request, "core/ai_entry.html", {"active_session": session})


def grader_entry_point(request: HttpRequest) -> HttpResponse:
    """Entry point for Grader sessions (participant access)."""
    from .models import GraderSession
    from .forms import ParticipantIdForm

    session = GraderSession.get_active()
    if request.method == "POST":
        form = ParticipantIdForm(request.POST)
        if form.is_valid():
            participant_id = form.cleaned_data["participant_id"]
            if participant_id == 0:
                return redirect("grader_moderator_dashboard")
            return redirect("grader_user", user_id=participant_id)
    else:
        form = ParticipantIdForm()

    return render(
        request,
        "core/grader_entry.html",
        {
            "form": form,
            "active_session": session,
            "deliberation_mode": "grader",
        },
    )


def ai_moderator_dashboard(request: HttpRequest) -> HttpResponse:
    """Moderator dashboard for AI-AI deliberation."""
    from .forms import AIDeliberationSessionForm, AISessionSelectionForm
    from .models import AIDeliberationSession

    sessions = AIDeliberationSession.objects.all().order_by("-updated_at")
    selected_session: Optional[AIDeliberationSession] = None

    # Check for session_id in query parameters
    query_session_id = request.GET.get("session_id")
    if query_session_id:
        try:
            selected_session = sessions.filter(pk=int(query_session_id)).first()
            if selected_session:
                request.session["ai_moderator_selected_session_id"] = int(query_session_id)
        except (TypeError, ValueError):
            pass

    # Fall back to session-stored selection or active session
    if selected_session is None:
        selected_session_id = request.session.get("ai_moderator_selected_session_id")
        if selected_session_id:
            selected_session = sessions.filter(pk=selected_session_id).first()

    if selected_session is None:
        selected_session = sessions.filter(is_active=True).order_by("-updated_at").first()

    session_form: AIDeliberationSessionForm

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "load_session":
            target_id = request.POST.get("session_id")
            if target_id:
                try:
                    request.session["ai_moderator_selected_session_id"] = int(target_id)
                except (TypeError, ValueError):
                    messages.error(request, "Unable to load the requested session.")
                else:
                    return redirect("ai_moderator_dashboard")
            else:
                request.session.pop("ai_moderator_selected_session_id", None)
                return redirect("ai_moderator_dashboard")

        if action in {"save_session", "create_session"}:
            instance = selected_session if (action == "save_session" and selected_session) else None
            session_form = AIDeliberationSessionForm(request.POST, instance=instance)
            if session_form.is_valid():
                new_session = session_form.save(commit=False)
                if not new_session.pk:
                    new_session.is_active = False
                new_session.save()
                request.session["ai_moderator_selected_session_id"] = new_session.pk
                messages.success(request, "AI session saved.")
                return redirect("ai_moderator_dashboard")
            else:
                # Form is invalid; show errors and re-render
                messages.error(request, "Please fix the errors below.")
        elif action == "activate_session":
            if selected_session is None:
                messages.error(request, "Select a session before activating it.")
            else:
                selected_session.activate()
                request.session["ai_moderator_selected_session_id"] = selected_session.pk
                messages.success(request, f"AI session {selected_session.s_id} is now active.")
                return redirect("ai_moderator_dashboard")
        elif action == "run_deliberation":
            if selected_session is None:
                messages.error(request, "Select a session before running deliberation.")
            else:
                # Run the deliberation
                from .services.ai_deliberation_service import AIDeliberationService

                try:
                    service = AIDeliberationService(selected_session)
                    run = service.start_deliberation(blocking=False)
                    messages.success(request, "Deliberation started. This page will open the live transcript in a new tab.")
                    return redirect("ai_deliberation_results", run_id=run.pk)
                except Exception as exc:
                    messages.error(request, f"Error running deliberation: {exc}")
                    return redirect("ai_moderator_dashboard")
        elif action == "run_rag":
            if selected_session is None:
                messages.error(request, "Save or select a session before rebuilding the index.")
            else:
                # Support optional file upload (.txt or .csv) or inline knowledge_base text
                raw_text = None
                uploaded = request.FILES.get('knowledge_file')
                if uploaded is not None:
                    try:
                        content = uploaded.read()
                        try:
                            text = content.decode('utf-8')
                        except Exception:
                            text = content.decode('latin-1')
                        name = (uploaded.name or '').lower()
                        if name.endswith('.csv'):
                            reader = csv.reader(io.StringIO(text))
                            rows = [', '.join([cell for cell in row]) for row in reader]
                            raw_text = '\n'.join(rows)
                        else:
                            raw_text = text
                    except Exception as exc:
                        messages.error(request, f"Failed to read uploaded file: {exc}")
                        return redirect("ai_moderator_dashboard")
                else:
                    raw_text = request.POST.get('knowledge_base') or None

                try:
                    chunk_count = RagService(selected_session).build_index(raw_text=raw_text)
                except Exception as exc:
                    messages.error(request, f"Failed to rebuild the RAG index: {exc}")
                else:
                    if chunk_count == 0:
                        messages.warning(request, "RAG index is empty. Add knowledge base content before rebuilding.")
                    else:
                        messages.success(request, f"RAG index rebuilt with {chunk_count} knowledge snippets.")
                return redirect("ai_moderator_dashboard")
    
    # Initialize session_form if not already set
    if "session_form" not in locals():
        session_form = AIDeliberationSessionForm(instance=selected_session)

    selection_initial = {
        "session_id": str(selected_session.pk) if selected_session else "",
    }
    selection_form = AISessionSelectionForm(
        request.POST if request.method == "POST" else None,
        sessions=sessions,
        initial=selection_initial,
    )

    context: Dict[str, Any] = {
        "selection_form": selection_form,
        "session_form": session_form,
        "selected_session": selected_session,
        "sessions": sessions,
    }
    return render(request, "core/ai_moderator_dashboard.html", context)


def grader_moderator_dashboard(request: HttpRequest) -> HttpResponse:
    """Moderator dashboard for Grader sessions."""
    from .forms import GraderSessionForm, GraderSessionSelectionForm
    from .models import GraderSession, GraderResponse
    from .services.rag_service import RagService

    sessions = GraderSession.objects.all().order_by("-updated_at")
    selected_session = None

    query_session_id = request.GET.get("session_id")
    if query_session_id:
        try:
            selected_session = sessions.filter(pk=int(query_session_id)).first()
            if selected_session:
                request.session["grader_moderator_selected_session_id"] = int(query_session_id)
        except (TypeError, ValueError):
            pass

    if selected_session is None:
        selected_session_id = request.session.get("grader_moderator_selected_session_id")
        if selected_session_id:
            selected_session = sessions.filter(pk=selected_session_id).first()

    if selected_session is None:
        selected_session = sessions.filter(is_active=True).order_by("-updated_at").first()

    session_form: GraderSessionForm

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "load_session":
            target_id = request.POST.get("session_id")
            if target_id:
                try:
                    request.session["grader_moderator_selected_session_id"] = int(target_id)
                except (TypeError, ValueError):
                    messages.error(request, "Unable to load the requested session.")
                else:
                    return redirect("grader_moderator_dashboard")
            else:
                request.session.pop("grader_moderator_selected_session_id", None)
                return redirect("grader_moderator_dashboard")

        if action in {"save_session", "create_session"}:
            instance = selected_session if (action == "save_session" and selected_session) else None
            session_form = GraderSessionForm(request.POST, instance=instance)
            if session_form.is_valid():
                new_session = session_form.save(commit=False)
                if not new_session.pk:
                    new_session.is_active = False
                new_session.save()
                request.session["grader_moderator_selected_session_id"] = new_session.pk
                messages.success(request, "Grader session saved.")
                return redirect("grader_moderator_dashboard")
            else:
                messages.error(request, "Please fix the errors below.")
        elif action == "activate_session":
            if selected_session is None:
                messages.error(request, "Select a session before activating it.")
            else:
                selected_session.activate()
                request.session["grader_moderator_selected_session_id"] = selected_session.pk
                messages.success(request, f"Grader session {selected_session.s_id} is now active.")
                return redirect("grader_moderator_dashboard")
        elif action == "run_rag":
            if selected_session is None:
                messages.error(request, "Save or select a session before rebuilding the index.")
            else:
                raw_text = None
                uploaded = request.FILES.get('knowledge_file')
                if uploaded is not None:
                    try:
                        content = uploaded.read()
                        try:
                            text = content.decode('utf-8')
                        except Exception:
                            text = content.decode('latin-1')
                        name = (uploaded.name or '').lower()
                        if name.endswith('.csv'):
                            import csv, io
                            reader = csv.reader(io.StringIO(text))
                            rows = [', '.join([cell for cell in row]) for row in reader]
                            raw_text = '\n'.join(rows)
                        else:
                            raw_text = text
                    except Exception as exc:
                        messages.error(request, f"Failed to read uploaded file: {exc}")
                        return redirect("grader_moderator_dashboard")
                else:
                    raw_text = request.POST.get('knowledge_base') or None

                try:
                    chunk_count = RagService(selected_session).build_index(raw_text=raw_text)
                except Exception as exc:
                    messages.error(request, f"Failed to rebuild the RAG index: {exc}")
                else:
                    if chunk_count == 0:
                        messages.warning(request, "RAG index is empty. Add knowledge base content before rebuilding.")
                    else:
                        messages.success(request, f"RAG index rebuilt with {chunk_count} knowledge snippets.")
                return redirect("grader_moderator_dashboard")
        elif action == "analyze":
            # Run analysis across all responses for the selected session
            if not selected_session:
                messages.error(request, "Select a session before analyzing.")
            else:
                # Compute averages and call the LLM to summarize reasons per feature
                from .services.openai_client import get_openai_client
                client = get_openai_client()
                responses = list(GraderResponse.objects.filter(session=selected_session))
                questions = selected_session.get_question_sequence()
                if not responses:
                    messages.warning(request, "No grader responses to analyze.")
                    return redirect("grader_moderator_dashboard")

                # Compute average scores
                scores_by_q = [[] for _ in questions]
                comments_by_q = [[] for _ in questions]
                for resp in responses:
                    for i, q in enumerate(questions):
                        try:
                            score = int(resp.scores[i])
                        except Exception:
                            score = None
                        if score is not None:
                            scores_by_q[i].append(score)
                        try:
                            reason = str(resp.reasons[i]).strip()
                        except Exception:
                            reason = ""
                        if reason:
                            comments_by_q[i].append(reason)

                averages = []
                for lst in scores_by_q:
                    if lst:
                        averages.append(sum(lst) / len(lst))
                    else:
                        averages.append(None)

                # Build prompts to summarize comments per question
                summary_texts = []
                for idx, q in enumerate(questions):
                    concat = "\n\n".join(comments_by_q[idx])[:4000]
                    system_prompt = f"You are summarizing grader feedback for a specific feature/question. Produce a concise markdown summary of the reasons provided by graders."
                    user_prompt = f"Question: {q}\n\nResponses:\n{concat}\n\nProvide a short summary (3-6 sentences) capturing common themes and representative points."
                    
                    # Inject moderator's LLM instructions if provided
                    if selected_session.user_instructions:
                        user_prompt += f"\n\nModerator instructions: {selected_session.user_instructions}"
                    
                    messages_payload = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ]
                    try:
                        completion = client.chat.completions.create(
                            model=settings.OPENAI_MODEL_NAME,
                            messages=messages_payload,
                            temperature=0.6,
                        )
                        summary = completion.choices[0].message.content or ""
                    except Exception as exc:
                        summary = f"(LLM summary failed: {exc})"
                    summary_texts.append(summary)

                # Save analysis into session.moderator_summary (simple markdown)
                md_lines = [f"# Analysis for {selected_session.topic}\n"]
                for idx, q in enumerate(questions):
                    avg = averages[idx]
                    avg_str = f"{avg:.2f}" if avg is not None else "No scores"
                    md_lines.append(f"## Question {idx+1}: {q}\n")
                    md_lines.append(f"**Average score:** {avg_str}\n")
                    md_lines.append(f"**Summary of reasons:**\n{summary_texts[idx]}\n")

                selected_session.analysis_markdown = "\n".join(md_lines)
                selected_session.save(update_fields=["analysis_markdown", "updated_at"])
                messages.success(request, "Analysis complete. Summary available in the analysis panel.")
                return redirect("grader_moderator_dashboard")

    if "session_form" not in locals():
        session_form = GraderSessionForm(instance=selected_session)

    selection_initial = {"session_id": str(selected_session.pk) if selected_session else ""}
    selection_form = GraderSessionSelectionForm(
        request.POST if request.method == "POST" else None,
        sessions=sessions,
        initial=selection_initial,
    )

    context = {
        "selection_form": selection_form,
        "session_form": session_form,
        "selected_session": selected_session,
        "sessions": sessions,
        "deliberation_mode": "grader",
    }
    return render(request, "core/grader_moderator_dashboard.html", context)


def grader_user_view(request: HttpRequest, user_id: int) -> HttpResponse:
    """User-facing grader page where a participant assigns scores and reasons."""
    from .models import GraderSession, GraderResponse
    from .forms import GraderResponseForm

    session = GraderSession.get_active()
    if not session:
        messages.error(request, "No active grader session is available.")
        return redirect("system_choice")

    questions = session.get_question_sequence()

    # Build a simple dynamic form on the fly
    if request.method == "POST":
        # Extract the scores and reasons
        scores = []
        reasons = []
        for i in range(len(questions)):
            s = request.POST.get(f"score_{i}")
            try:
                sv = int(s)
            except Exception:
                sv = None
            scores.append(sv)
            reasons.append(request.POST.get(f"reason_{i}", ""))

        additional = request.POST.get("additional_comments", "")

        # Save to DB (create or update if exists)
        resp, _ = GraderResponse.objects.update_or_create(
            session=session,
            user_id=user_id,
            defaults={
                "scores": scores,
                "reasons": reasons,
                "additional_comments": additional,
            },
        )
        messages.success(request, "Your grader responses have been saved. Thank you.")
        return redirect("system_choice")

    # Pre-fill if response exists
    existing = GraderResponse.objects.filter(session=session, user_id=user_id).first()
    initial_scores = existing.scores if existing else [None] * len(questions)
    initial_reasons = existing.reasons if existing else [""] * len(questions)

    # Build combined question data for template: (index, question, score, reason)
    questions_data = []
    for i, q in enumerate(questions):
        questions_data.append((i, q, initial_scores[i] if i < len(initial_scores) else None, initial_reasons[i] if i < len(initial_reasons) else ""))

    context = {
        "session": session,
        "questions_data": questions_data,
        "additional": existing.additional_comments if existing else "",
        "user_id": user_id,
        "deliberation_mode": "grader",
    }
    return render(request, "core/grader_user_conversation.html", context)


def ai_deliberation_results(request: HttpRequest, run_id: int) -> HttpResponse:
    """Display the results of an AI deliberation run."""
    from .models import AIDebateRun

    try:
        run = AIDebateRun.objects.get(pk=run_id)
    except AIDebateRun.DoesNotExist:
        messages.error(request, "Debate run not found.")
        return redirect("ai_moderator_dashboard")

    session = run.session

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "summarize":
            from .services.ai_deliberation_service import AIDeliberationService

            try:
                if not run.completed:
                    messages.warning(request, "Deliberation is still running. Please wait until the transcript is ready before generating a summary.")
                    return redirect("ai_deliberation_results", run_id=run_id)

                service = AIDeliberationService(session)
                summary_text = service.generate_summary(run)

                if summary_text:
                    # Create or update summary record
                    from .models import AIDebateSummary

                    summary_obj, _ = AIDebateSummary.objects.get_or_create(session=session)
                    summary_obj.topic = session.topic
                    summary_obj.description = session.description
                    summary_obj.objective_questions = session.objective_questions
                    summary_obj.personas = session.personas
                    summary_obj.summary_markdown = summary_text
                    summary_obj.save()

                    messages.success(request, "Summary generated and saved.")
                    return redirect("ai_deliberation_results", run_id=run_id)
            except Exception as exc:
                messages.error(request, f"Error generating summary: {exc}")

    # Format transcript for display in chat-like order per question
    transcript_threads: list[dict[str, object]] = []
    if run.transcript:
        thread_lookup: Dict[int, dict[str, object]] = {}
        question_order: List[int] = []

        for turn in run.transcript:
            q_idx = int(turn.get("question_index", 0))
            question_text = turn.get("question", "")

            if q_idx not in thread_lookup:
                thread_lookup[q_idx] = {
                    "question_index": q_idx,
                    "question": question_text,
                    "messages": [],
                }
                question_order.append(q_idx)

            stage = turn.get("stage")
            if not stage and "round" in turn:
                round_value = turn.get("round")
                if round_value == 1:
                    stage = "initial"
                elif round_value == 2:
                    stage = "critique"

            stage_label = None
            if stage == "initial":
                stage_label = "Initial Response"
            elif stage == "critique":
                stage_label = "Critique"

            message = {
                "persona": turn.get("persona", ""),
                "content": turn.get("content") or turn.get("opinion", ""),
                "stage": stage,
                "stage_label": stage_label,
                "peer_opinions": turn.get("peer_opinions", []),
            }

            thread_lookup[q_idx]["messages"].append(message)

        transcript_threads = [thread_lookup[idx] for idx in question_order]

    # Get summary if it exists
    from .models import AIDebateSummary

    summary_obj = AIDebateSummary.objects.filter(session=session).first()

    context = {
        "session": session,
        "run": run,
        "transcript_threads": transcript_threads,
        "summary": summary_obj,
    }
    return render(request, "core/ai_deliberation_results.html", context)


def _get_or_create_default_ai_session() -> "AIDeliberationSession":
    """Get or create a default AI deliberation session."""
    from .models import AIDeliberationSession

    session = AIDeliberationSession.objects.filter(is_active=True).order_by("-updated_at").first()
    if not session:
        session = AIDeliberationSession.objects.create(
            s_id="ai-default",
            topic="Default AI Deliberation",
        )
    return session


def grader_export_csv(request: HttpRequest, session_id: int) -> HttpResponse:
    """Export grader responses as CSV for a given session."""
    from .models import GraderSession, GraderResponse

    try:
        session = GraderSession.objects.get(pk=session_id)
    except GraderSession.DoesNotExist:
        messages.error(request, "Grader session not found.")
        return redirect("grader_moderator_dashboard")

    questions = session.get_question_sequence()
    responses = GraderResponse.objects.filter(session=session).order_by("user_id")

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row: User ID, then each question's score and reason columns
    header = ["User ID"]
    for i, q in enumerate(questions):
        header.append(f"Q{i+1} Score")
        header.append(f"Q{i+1} Reason")
    header.append("Additional Comments")
    writer.writerow(header)

    # Data rows
    for resp in responses:
        row = [resp.user_id]
        for i, q in enumerate(questions):
            score = resp.scores[i] if i < len(resp.scores) else ""
            reason = resp.reasons[i] if i < len(resp.reasons) else ""
            row.append(score)
            row.append(reason)
        row.append(resp.additional_comments or "")
        writer.writerow(row)

    # Return as file download
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename=grader_{session.s_id}_{session.pk}.csv"
    return response


def discussion_grader_export_csv(request: HttpRequest, session_id: int) -> HttpResponse:
    """Legacy: Export grader responses. Now redirects to unified export."""
    # Redirect to new unified ratings export
    return redirect("export_ratings_csv", session_id=session_id)


def discussion_grader_user_view(request: HttpRequest, user_id: int) -> HttpResponse:
    """Legacy: Participant grader view. Now redirects to unified conversation view.
    
    Grading is now handled inline in the user_conversation view.
    """
    messages.info(request, "Grading questions are now integrated into the main conversation flow.")
    return redirect("user_conversation", user_id=user_id)


# ============================================================================
# UNIFIED EXPORT VIEWS (for new unified question format)
# ============================================================================


def export_user_csv(request: HttpRequest, session_id: int, user_id: int) -> HttpResponse:
    """Export a single user's responses as CSV (question + response columns)."""
    try:
        session = DiscussionSession.objects.get(pk=session_id)
    except DiscussionSession.DoesNotExist:
        messages.error(request, "Session not found.")
        return redirect("moderator_dashboard")

    try:
        conversation = UserConversation.objects.get(session=session, user_id=user_id)
    except UserConversation.DoesNotExist:
        messages.error(request, f"No conversation found for user {user_id}.")
        return redirect("moderator_dashboard")

    all_questions = session.get_all_questions()
    responses = conversation.get_all_responses()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(["Question #", "Question Type", "Question Text", "Score", "Reason/Response", "Discussion Messages"])

    # Build a lookup of responses by question index
    response_lookup = {r.get("question_index"): r for r in responses}

    for i, q in enumerate(all_questions):
        resp = response_lookup.get(i, {})
        q_text = q.get("text", "")
        q_type = q.get("type", "discussion")

        if q_type == "grading":
            score = resp.get("score", "")
            reason = resp.get("reason", "")
            writer.writerow([i + 1, q_type.capitalize(), q_text, score, reason, ""])
        else:
            # For discussion questions, concatenate the history
            history = resp.get("discussion_history", [])
            if history:
                history_text = " | ".join([f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in history])
            else:
                history_text = ""
            writer.writerow([i + 1, q_type.capitalize(), q_text, "", "", history_text])

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename=user_{user_id}_{session.s_id}_{session.pk}.csv"
    return response


def export_ratings_csv(request: HttpRequest, session_id: int) -> HttpResponse:
    """Export overall grading ratings as CSV (users x questions matrix with averages)."""
    try:
        session = DiscussionSession.objects.get(pk=session_id)
    except DiscussionSession.DoesNotExist:
        messages.error(request, "Session not found.")
        return redirect("moderator_dashboard")

    all_questions = session.get_all_questions()
    grading_questions = [(i, q) for i, q in enumerate(all_questions) if q.get("type") == "grading"]

    if not grading_questions:
        messages.warning(request, "No grading questions found in this session.")
        return redirect("moderator_dashboard")

    conversations = UserConversation.objects.filter(session=session).order_by("user_id")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row: User ID, Q1 Score, Q1 Reason, Q2 Score, Q2 Reason, ...
    header = ["User ID"]
    for idx, q in grading_questions:
        q_num = idx + 1
        header.append(f"Q{q_num} Score")
        header.append(f"Q{q_num} Reason")
    writer.writerow(header)

    # Data rows for each user
    all_scores: Dict[int, List[Optional[int]]] = {}  # question_index -> list of scores

    for conv in conversations:
        responses = conv.get_all_responses()
        response_lookup = {r.get("question_index"): r for r in responses}

        row = [conv.user_id]
        for q_idx, q in grading_questions:
            resp = response_lookup.get(q_idx, {})
            score = resp.get("score")
            reason = resp.get("reason", "")
            row.append(score if score is not None else "")
            row.append(reason)

            # Track for averages
            if q_idx not in all_scores:
                all_scores[q_idx] = []
            if score is not None:
                all_scores[q_idx].append(score)

        writer.writerow(row)

    # Average row
    avg_row: List[Any] = ["AVERAGE"]
    for q_idx, q in grading_questions:
        scores = all_scores.get(q_idx, [])
        if scores:
            avg = sum(scores) / len(scores)
            avg_row.append(f"{avg:.2f}")
        else:
            avg_row.append("")
        avg_row.append("")  # No average for reason column
    writer.writerow(avg_row)

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename=ratings_{session.s_id}_{session.pk}.csv"
    return response


def download_summary_json(request: HttpRequest, session_id: int) -> HttpResponse:
    """Download the session summary as a JSON file."""
    try:
        session = DiscussionSession.objects.get(pk=session_id)
    except DiscussionSession.DoesNotExist:
        messages.error(request, "Session not found.")
        return redirect("moderator_dashboard")

    all_questions = session.get_all_questions()
    conversations = UserConversation.objects.filter(session=session).order_by("user_id")

    # Build comprehensive summary
    summary: Dict[str, Any] = {
        "session_id": session.s_id,
        "session_pk": session.pk,
        "topic": session.topic,
        "description": session.description,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "questions": all_questions,
        "moderator_summary": None,
        "moderator_temp": session.moderator_temp or None,
        "users": [],
        "grading_statistics": {},
    }

    # Parse moderator summary if available
    if session.moderator_summary:
        try:
            summary["moderator_summary"] = json.loads(session.moderator_summary)
        except json.JSONDecodeError:
            summary["moderator_summary"] = session.moderator_summary

    # Collect user data
    grading_questions = [(i, q) for i, q in enumerate(all_questions) if q.get("type") == "grading"]
    all_scores: Dict[int, List[int]] = {q_idx: [] for q_idx, _ in grading_questions}

    for conv in conversations:
        responses = conv.get_all_responses()
        user_data: Dict[str, Any] = {
            "user_id": conv.user_id,
            "active": conv.active,
            "message_count": conv.message_count,
            "responses": responses,
            "views_markdown": conv.views_markdown or None,
        }
        summary["users"].append(user_data)

        # Collect grading scores for stats
        response_lookup = {r.get("question_index"): r for r in responses}
        for q_idx, _ in grading_questions:
            resp = response_lookup.get(q_idx, {})
            score = resp.get("score")
            if score is not None:
                all_scores[q_idx].append(score)

    # Calculate grading statistics
    for q_idx, scores in all_scores.items():
        q_data = all_questions[q_idx] if q_idx < len(all_questions) else {}
        stats: Dict[str, Any] = {
            "question_index": q_idx,
            "question_text": q_data.get("text", ""),
            "response_count": len(scores),
        }
        if scores:
            stats["average"] = sum(scores) / len(scores)
            stats["min"] = min(scores)
            stats["max"] = max(scores)
        else:
            stats["average"] = None
            stats["min"] = None
            stats["max"] = None
        summary["grading_statistics"][f"q{q_idx + 1}"] = stats

    response = HttpResponse(
        json.dumps(summary, indent=2, ensure_ascii=False),
        content_type="application/json",
    )
    response["Content-Disposition"] = f"attachment; filename=summary_{session.s_id}_{session.pk}.json"
    return response


def download_user_summary_markdown(request: HttpRequest, session_id: int, user_id: int) -> HttpResponse:
    """Download an individual user's final analysis as a markdown file with metadata."""
    try:
        session = DiscussionSession.objects.get(pk=session_id)
    except DiscussionSession.DoesNotExist:
        messages.error(request, "Session not found.")
        return redirect("moderator_dashboard")

    try:
        conversation = UserConversation.objects.get(session=session, user_id=user_id)
    except UserConversation.DoesNotExist:
        messages.error(request, f"No conversation found for user {user_id}.")
        return redirect("moderator_dashboard")

    # Build comprehensive markdown with metadata
    markdown_content = f"""# User {user_id} - Final Analysis
## Session: {session.topic}
**Session ID:** {session.s_id}  
**Date:** {conversation.updated_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.updated_at else 'N/A'}

---

## Metadata

- **Total Messages:** {conversation.message_count}
- **Content Length:** {conversation.content_length} words
- **Termination Reason:** {conversation.termination_reason or 'N/A'}
- **Unique Concepts Discussed:** {len(conversation.unique_concepts or [])}

### Key Concepts

"""
    
    # Add unique concepts as a list
    if conversation.unique_concepts:
        for concept in conversation.unique_concepts:
            markdown_content += f"- {concept}\n"
    else:
        markdown_content += "*No concepts extracted*\n"
    
    markdown_content += f"""
---

## Analysis

{conversation.views_markdown or '*No final analysis available*'}

---

*Generated by DiscussChat - AI-Facilitated Deliberation Platform*
"""

    response = HttpResponse(markdown_content, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f"attachment; filename=user_{user_id}_{session.s_id}_analysis.md"
    return response
