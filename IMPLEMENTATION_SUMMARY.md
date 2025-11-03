# Grader Feature - Implementation Summary

## Overview
A new **Grader** deliberation mode has been successfully implemented in the AI Deliberation Service. This feature allows moderators to create scoring/grading sessions where participants assign numeric ratings (1–10) to objective features and provide written justification.

## Files Modified

### 1. Core Models (`chatbot_site/core/models.py`)
**Added:**
- `GraderSession` model – represents a grading evaluation session
  - Fields: s_id, topic, description, objective_questions, knowledge_base, rag_chunk_count, rag_last_built_at, user_instructions, is_active, created_at, updated_at
  - Methods: get_question_sequence(), get_active(), activate()
  
- `GraderResponse` model – stores participant grading submissions
  - Fields: session (FK), user_id, scores, reasons, additional_comments, submitted_at
  - Unique constraint: (session, user_id) ensures one response per user per session

### 2. Forms (`chatbot_site/core/forms.py`)
**Added:**
- `GraderSessionForm` – form for creating/editing grader sessions with dynamic question management
- `GraderSessionSelectionForm` – dropdown selector for loading sessions
- `GraderResponseForm` – base form class for participant submissions (instantiated dynamically)

### 3. Views (`chatbot_site/core/views.py`)
**Added:**
- `grader_entry_point()` – entry page for moderators (redirects to dashboard)
- `grader_moderator_dashboard()` – full moderator dashboard with:
  - Session creation/editing
  - Question builder with reordering
  - RAG management
  - Response analysis engine (calculates averages, calls OpenAI for summaries)
  - CSV download link
  
- `grader_user_view()` – participant-facing grading form with:
  - Score input (1–10) for each question
  - Reason text area for each question
  - Additional comments field
  - Submit/save functionality
  
- `grader_export_csv()` – exports all responses as CSV with user IDs, scores, reasons, and comments

### 4. URL Routes (`chatbot_site/core/urls.py`)
**Added:**
```python
path('grader/', views.grader_entry_point, name='grader_entry'),
path('grader/moderator/', views.grader_moderator_dashboard, name='grader_moderator_dashboard'),
path('grader/user/<int:user_id>/', views.grader_user_view, name='grader_user'),
path('grader/export/<int:session_id>/', views.grader_export_csv, name='grader_export'),
```

### 5. Templates
**Created:**
- `grader_entry.html` – entry point landing page
- `grader_moderator_dashboard.html` – moderator control panel with:
  - Session selector dropdown
  - Session form (s_id, topic, description)
  - Question builder with add/remove/reorder buttons
  - Knowledge base field
  - User instructions field
  - Action buttons: Save, Save As New, Activate, Run RAG, Analyze Responses
  - CSV download link
  - Sessions list sidebar
  
- `grader_user_conversation.html` – participant grading form with:
  - Session topic and description display
  - Score input and reason textarea for each question
  - Additional comments field
  - Submit button

**Modified:**
- `system_choice.html` – added "Grader" option button alongside Human-AI and AI-AI

### 6. Django Admin (`chatbot_site/core/admin.py`)
**Added:**
- `GraderSessionAdmin` – admin interface for GraderSession (list display, filters, search)
- `GraderResponseAdmin` – admin interface for GraderResponse (list display, search)

### 7. Database Migration (`chatbot_site/core/migrations/0013_add_grader_models.py`)
**Created:** Migration to create `core_gradersession` and `core_graderresponse` tables with all fields and constraints

### 8. Documentation (`GRADER_FEATURE.md`)
**Created:** Comprehensive feature documentation including:
- Feature overview
- Database schema
- URL routes
- Moderator workflow
- Participant workflow
- API & form components
- Analysis engine description
- CSV export format
- Integration notes
- Example session setup

## Key Features

1. **Large Description Support**
   - Markdown-formatted descriptions (up to 6000+ words)
   - Properly rendered in participant grading form

2. **Flexible Question Setup**
   - Dynamic question builder with add/reorder/remove
   - Questions stored as JSON array

3. **Score Collection**
   - Each question gets a 1–10 score + written reason
   - Additional free-form comments allowed
   - Responses validated and stored per user per session

4. **AI-Powered Analysis**
   - Calculates average score for each feature
   - Calls OpenAI to summarize participant reasons per question
   - Generates markdown-formatted report

5. **CSV Export**
   - One row per participant
   - Columns: User ID, Q1 Score, Q1 Reason, Q2 Score, Q2 Reason, ..., Additional Comments
   - Downloadable as attachment

6. **Knowledge Base Integration**
   - Optional RAG support
   - Same infrastructure as other session types

## Workflow

### Moderator
1. Navigate to Deliberation System Choice → select **Grader**
2. Create new session with topic, description, questions
3. Activate session
4. Share grader URL `/grader/user/<user_id>/` with participants
5. Once responses collected, click **Analyze Responses**
6. View average scores and AI-generated summaries
7. Download CSV of all responses

### Participant
1. Navigate to `/grader/user/<their_id>/`
2. Read session description
3. For each objective question: enter score (1–10) + reason
4. Add optional additional comments
5. Click Submit Scores
6. Get success confirmation

## Testing Checklist

- [x] Models created and migrated
- [x] Forms validate properly
- [x] Views handle GET/POST requests
- [x] URLs route correctly
- [x] Templates render without errors
- [x] Admin registration complete
- [x] CSV export generates correct format
- [x] Analysis calculates averages and calls OpenAI
- [x] Markdown description renders properly
- [x] Question builder JavaScript works

## Technical Highlights

- **Database Design**: Efficient JSONField storage for scores/reasons with unique constraints
- **Form Handling**: Dynamic question list with client-side JavaScript for reordering
- **Analysis Logic**: Batch processes all responses, calls LLM for summaries
- **CSV Generation**: Streaming CSV with proper escaping and headers
- **RAG Support**: Plugs into existing RagService infrastructure
- **Session Activation**: Only one active session at a time, consistent with other modes

## Files Changed

| File | Type | Changes |
|------|------|---------|
| `chatbot_site/core/models.py` | Model | +GraderSession, +GraderResponse |
| `chatbot_site/core/forms.py` | Form | +GraderSessionForm, +GraderSessionSelectionForm, +GraderResponseForm |
| `chatbot_site/core/views.py` | View | +5 grader views |
| `chatbot_site/core/urls.py` | Route | +4 grader URLs |
| `chatbot_site/core/admin.py` | Admin | +2 admin registrations |
| `chatbot_site/templates/core/system_choice.html` | Template | Updated with Grader button |
| `chatbot_site/templates/core/grader_entry.html` | Template | **Created** |
| `chatbot_site/templates/core/grader_moderator_dashboard.html` | Template | **Created** |
| `chatbot_site/templates/core/grader_user_conversation.html` | Template | **Created** |
| `chatbot_site/core/migrations/0013_add_grader_models.py` | Migration | **Created** |
| `GRADER_FEATURE.md` | Documentation | **Created** |

## Next Steps (Optional Enhancements)

1. **Response Analytics Dashboard** – visualizations (charts, distributions)
2. **Comparative Analysis** – compare across multiple sessions
3. **Weighted Scoring** – assign importance weights to questions
4. **Conditional Questions** – show/hide questions based on prior answers
5. **Email Invitations** – automated participant invites with tracking
6. **Result Presentation** – formatted reports for sharing with stakeholders
7. **Duplicate Submissions** – track which users have/haven't submitted
8. **Response Timestamps** – track submission timing for deadlines

---

**Implementation Date:** November 3, 2025
**Status:** Ready for testing and deployment
