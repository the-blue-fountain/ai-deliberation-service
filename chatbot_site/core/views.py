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
    session = DiscussionSession.get_active()
    conversation, _ = UserConversation.objects.get_or_create(session=session, user_id=user_id)

    # Determine the current question context for this participant
    temp_snapshot = conversation.scratchpad or ""
    views_snapshot = conversation.views_markdown or ""

    result_payload: Optional[Dict[str, Any]] = None

    if request.method == "POST":
        action = request.POST.get("action", "send")
        if action == "stop":
            service = UserConversationService(session, conversation)
            try:
                final_views = service.stop_conversation()
            except Exception as exc:  # pragma: no cover - defensive
                messages.error(request, f"Unable to stop the conversation: {exc}")
            else:
                messages.info(request, "Conversation stopped. Final views document generated.")
                views_snapshot = final_views
                conversation.refresh_from_db()
            form = UserMessageForm()
            temp_snapshot = conversation.scratchpad
        else:
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
                except Exception as exc:  # pragma: no cover - defensive
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
                    form = UserMessageForm()

                    if result.ended:
                        end_reason = result.end_reason or ""
                        if end_reason == "no_new_limit":
                            messages.info(
                                request,
                                "Conversation closed after reaching the moderator-defined limit for consecutive responses without new information on the final question.",
                            )
                        elif end_reason == "followup_limit":
                            messages.info(
                                request,
                                "Conversation closed after reaching the moderator-defined follow-up limit on the final question.",
                            )
                        elif end_reason == "message_limit":
                            messages.info(request, "Conversation closed after reaching the 15 message limit.")
                        else:
                            messages.info(request, "Conversation closed.")
            else:
                messages.error(request, "Please enter a response before submitting.")
    else:
        form = UserMessageForm()

    question_sequence = session.get_question_sequence() if session else []
    current_question = session.get_objective_for_user(user_id, conversation=conversation) if session else ""
    question_total = len(question_sequence)
    current_index = conversation.current_question_index
    if current_question:
        question_position = min(current_index + 1, question_total)
    elif question_total:
        question_position = question_total
    else:
        question_position = 0

    if session and not current_question and conversation.active and question_total == 0:
        messages.info(
            request,
            "The moderator has not provided questions yet. Please wait before sharing details.",
        )

    next_question = ""
    if conversation.active and question_total and current_index + 1 < question_total:
        next_question = question_sequence[current_index + 1]

    followup_limit = session.question_followup_limit if session else 0
    followups_used = conversation.question_followups if current_question else 0
    followups_remaining = max(followup_limit - followups_used, 0) if followup_limit else 0

    no_new_limit = session.no_new_information_limit if session else 0
    no_new_streak = conversation.consecutive_no_new if current_question else 0
    no_new_remaining = max(no_new_limit - no_new_streak, 0) if no_new_limit else 0

    context = {
        "session": session,
        "conversation": conversation,
        "form": form,
        "history": conversation.history or [],
        "result": result_payload,
        "temp_snapshot": temp_snapshot,
        "views_snapshot": views_snapshot,
        "topic": session.topic,
        "question": current_question,
        "question_sequence": question_sequence,
        "question_total": question_total,
        "question_position": question_position,
        "question_next": next_question,
        "question_followup_limit": followup_limit,
        "question_followups_used": followups_used,
        "question_followups_remaining": followups_remaining,
        "no_new_information_limit": no_new_limit,
        "no_new_information_remaining": no_new_remaining,
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

