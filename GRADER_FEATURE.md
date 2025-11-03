# Grader Feature Documentation

## Overview

The **Grader** is a new deliberation mode added to the AI Deliberation Service. Unlike the AI-Human and AI-AI deliberation workflows, the Grader allows moderators to set up evaluation sessions where participants assign numeric scores (1–10) to objective features/questions, provide written reasons for each score, and submit optional additional comments.

## Key Features

- **Moderator Setup**: Define a grading session with topic, description, and objective questions
- **Large Description Support**: Session descriptions support markdown formatting and can accommodate up to 6000+ words
- **Knowledge Base Integration**: Optional RAG (Retrieval-Augmented Generation) support for storing reference materials
- **Participant Scoring**: Users rate each objective question on a 1–10 scale with mandatory written reasons
- **Free-Form Comments**: Optional field for participants to add overall impressions or feedback
- **Analysis**: Moderators can click "Analyze Responses" to:
  - Compute average scores for each feature
  - Generate AI-powered summaries of participant reasons per question
  - View markdown-formatted analysis
- **CSV Export**: Download all responses as a spreadsheet with:
  - One row per participant
  - Columns for each question's score and reason
  - Additional comments column

## Database Schema

### GraderSession
Represents a grading evaluation session. Fields include:
- `s_id` (CharField, unique): Session identifier
- `topic` (CharField): Session title/topic
- `description` (TextField): Markdown-formatted session description
- `objective_questions` (JSONField): List of strings representing evaluation criteria
- `knowledge_base` (TextField): Optional reference materials for RAG
- `rag_chunk_count` (PositiveIntegerField): Number of RAG chunks built
- `rag_last_built_at` (DateTimeField): Timestamp of last RAG build
- `user_instructions` (TextField): Optional instructions for graders; also stores analysis results
- `is_active` (BooleanField): Whether this is the active session
- `created_at`, `updated_at` (DateTimeField): Timestamps

### GraderResponse
Stores one participant's grading submission for a session. Fields include:
- `session` (ForeignKey): Reference to the GraderSession
- `user_id` (PositiveIntegerField): Participant identifier
- `scores` (JSONField): List of integers (1–10) aligned with session questions
- `reasons` (JSONField): List of text explanations for each score
- `additional_comments` (TextField): Optional overall feedback
- `submitted_at` (DateTimeField): When the response was submitted
- **Unique Constraint**: `(session, user_id)` ensures one response per user per session

## URL Routes

| Route | View | Purpose |
|-------|------|---------|
| `/grader/` | `grader_entry_point` | Entry page; redirects to moderator dashboard |
| `/grader/moderator/` | `grader_moderator_dashboard` | Moderator dashboard for creating/managing sessions |
| `/grader/user/<user_id>/` | `grader_user_view` | User-facing grading form |
| `/grader/export/<session_id>/` | `grader_export_csv` | Download responses as CSV |

## Moderator Workflow

### 1. Entry Point
- Navigate to **Deliberation System Choice** → select **Grader**
- Redirected to grader moderator dashboard

### 2. Create Session
- Click **New Session** or **Save As New**
- Fill in:
  - **Session ID**: Unique identifier
  - **Topic**: Title for the evaluation
  - **Description**: Markdown-formatted background (supports up to 6000+ words)
  - **Objective Questions**: Add evaluation criteria (use "Add" button and reorder)
  - **Knowledge Base**: Optional reference materials
  - **User Instructions**: Optional guidance for graders

### 3. Activate & Configure
- **Save Changes**: Update existing session
- **Activate Session**: Mark this as the active session that users will access
- **Run RAG**: Build retrieval index from knowledge base (if provided)

### 4. Collect Responses
- Share the grader URL with participants: `/grader/user/<user_id>/`
- Each participant submits one response per session
- Responses are stored in the database

### 5. Analyze Results
- Click **Analyze Responses**
- System computes:
  - **Average score** for each question
  - **AI-generated summaries** of participant reasons per question
  - Displays markdown-formatted analysis
- Analysis is saved to the session's `user_instructions` field (visible as a note)

### 6. Export Data
- Click **Download Responses (CSV)**
- CSV file contains:
  - User ID
  - Each question's score and reason (two columns per question)
  - Additional comments
  - One row per participant

## Participant Workflow

### 1. Access Grading Form
- Navigate to `/grader/user/<user_id>/`
- Session description is displayed (markdown-rendered)

### 2. Submit Scores & Reasons
- For each objective question:
  - Enter a **score from 1 to 10** (1 = worst, 10 = best)
  - Write a **reason** explaining the score (text area)
- Optionally add **additional comments**
- Click **Submit Scores**

### 3. Confirmation
- Success message displayed
- User redirected to system choice page

## API & Form Components

### GraderSessionForm
- Handles creation/editing of GraderSession instances
- Dynamically manages the `objective_questions` JSON field via JavaScript
- Supports question reordering (Up/Down buttons) and removal

### GraderResponseForm
- Framework for accepting participant submissions
- Built dynamically by the view to match session questions

### GraderSessionSelectionForm
- Dropdown selector for loading existing sessions

## Analysis Engine

The "Analyze Responses" action:

1. **Retrieves** all GraderResponse records for the session
2. **Calculates** average score for each question
3. **For each question**, concatenates all participant reasons and calls OpenAI to summarize:
   - System prompt: "Summarize grader feedback for this feature"
   - User prompt: Concatenated reasons + request for 3–6 sentence summary
4. **Generates** markdown report with:
   - Question title
   - Average score (rounded to 2 decimals)
   - AI-generated summary of reasons
5. **Saves** report to session's `user_instructions` field (acts as session notes)

## CSV Export Format

Example CSV output:
```
User ID,Q1 Score,Q1 Reason,Q2 Score,Q2 Reason,Additional Comments
101,8,Good documentation and clear examples,7,Could use more edge case coverage,Overall solid product
102,9,Excellent API design,8,Performance could be better,Very impressed
```

## Integration with Existing System

- **System Choice Page**: Added "Grader" button alongside "AI-Human" and "AI-AI" options
- **Admin Interface**: GraderSession and GraderResponse are registered in Django admin for manual inspection/management
- **RAG Service**: Grader sessions support the same RAG infrastructure as other session types
- **Authentication**: Currently uses simple `user_id` routing; can be extended with Django permissions

## Technical Implementation Notes

- **Models**: Defined in `core/models.py`; migration `0013_add_grader_models.py` creates tables
- **Forms**: `GraderSessionForm`, `GraderResponseForm`, and `GraderSessionSelectionForm` in `core/forms.py`
- **Views**: All grader views in `core/views.py`
- **Templates**: 
  - `grader_entry.html` – entry point
  - `grader_moderator_dashboard.html` – moderator panel
  - `grader_user_conversation.html` – participant grading form
- **URLs**: Routes defined in `core/urls.py`
- **Admin**: Registration in `core/admin.py`

## Example Session Setup

**Topic**: "Mobile App Redesign Evaluation"

**Description**:
```markdown
# Mobile App Redesign Evaluation

We are evaluating our redesigned mobile app across several key dimensions.
Please provide honest feedback on each aspect below.

## Evaluation Context
The app was redesigned with a focus on:
- Improved navigation
- Streamlined workflows
- Enhanced accessibility
- Updated visual design
```

**Objective Questions**:
1. How well does the new navigation structure work?
2. Is the interface intuitive and easy to learn?
3. Does the app feel responsive and performant?
4. How satisfied are you with the overall visual design?

**Moderator receives**: Average score per question + summarized feedback + downloadable CSV with all responses

---

## Future Enhancements

- Comparative analysis across multiple grading sessions
- Visualizations (bar charts, distributions) for scores
- Weighted scoring (assign weights to questions)
- Conditional/branching questions based on prior responses
- Response validation (require minimum/maximum scores)
- Participant identity tracking with email invites
