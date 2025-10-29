from __future__ import annotations

import json
from typing import Any, Dict, Optional

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
                try:
                    chunk_count = RagService(selected_session).build_index()
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
                    }
                    temp_snapshot = conversation.scratchpad
                    if result.final_views_md is not None:
                        views_snapshot = result.final_views_md
                    form = UserMessageForm()

                    if result.ended:
                        if conversation.consecutive_no_new >= 2:
                            messages.info(
                                request,
                                "Conversation closed after two consecutive responses without new information.",
                            )
                        elif conversation.message_count >= 15:
                            messages.info(request, "Conversation closed after reaching the 15 message limit.")
            else:
                messages.error(request, "Please enter a response before submitting.")
    else:
        form = UserMessageForm()

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
    }
    return render(request, "core/user_conversation.html", context)
