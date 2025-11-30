# DiscussChat Features

This document lists all features of the application in simple terms for our team.

## System Overview

DiscussChat is a web platform with three different deliberation modes:
1. **Human-AI Deliberation** - Participants discuss topics with AI facilitation
2. **AI-AI Deliberation** - AI agents debate topics with different personas
3. **Grader System** - Participants score and evaluate discussion prompts

Users choose their mode on the system choice page at the root URL.

---

## 1. Human-AI Deliberation (Discussion Mode)

This is the core feature where real people discuss topics with AI facilitation.

### 1.1 Moderator Features

**Session Management**
- Create multiple discussion sessions with unique IDs
- Each session has a topic, description, and set of questions
- One session can be marked "active" at a time - this is what participants join
- Load existing sessions to edit or view
- Save changes or create new sessions from the dashboard

**Question Builder**
- Define an ordered list of objective questions for participants to answer
- AI-powered question suggestions: input a topic and get 4 suggested questions
- Questions can be reordered using up/down buttons
- Questions can be removed or added manually
- The question list is presented to all participants in the same order

**AI Prompt Customization**
- Customize how the bot talks to users (user system prompt)
- Customize how the bot analyzes all responses (moderator system prompt)
- Default prompts are provided but can be overridden per session
- These control bot personality, questioning style, and analysis approach

**Knowledge Base (RAG)**
- Upload reference documents (.txt or .csv files) or paste text directly
- The system chunks this content and builds a searchable index
- During conversations, relevant chunks are retrieved and shown to the AI
- Helps the AI give more informed, contextually accurate responses
- Can rebuild the index any time with new content

**Conversation Flow Control**
- Set how many follow-up responses are allowed per question (followup limit)
- Set how many consecutive "no new information" responses trigger advancement (no-new-info limit)
- These settings help pace the conversation and move participants through questions

**Participant Monitoring**
- View list of all participants who've joined the session
- See how many messages each person has sent
- Check whether conversations are still active or concluded
- See which participants have completed their final analysis

**Moderator Analysis**
- After participants finish, click "Analyze Responses" to synthesize all perspectives
- The system reads all participant final documents
- AI generates a structured summary organized by:
  - **Consensus** - areas where participants agree
  - **Disagreement** - divergent viewpoints
  - **Strength of sentiment** - emotional intensity indicators
  - **Confusion** - unclear or ambiguous topics
  - **Missing information** - gaps in coverage
- Internal reasoning is also captured for transparency
- Results displayed in markdown format on the dashboard

### 1.2 Participant Features

**Entry and Access**
- Participants enter via URL with their unique participant ID (non-zero number)
- Each participant gets their own conversation space within the active session
- Conversation history is preserved across page reloads

**Structured Question Flow**
- Participants see questions one at a time in the order set by the moderator
- Current question is displayed prominently at top of chat
- Progress indicator shows which question they're on (e.g., "Question 2 of 5")
- Can see what the next question will be
- Automatic advancement to next question when limits are reached

**Conversation Interface**
- Simple chat-style interface to respond to the AI
- See full conversation history (last 8 turns displayed in context)
- AI asks follow-up questions to dig deeper into responses
- AI detects new vs. repeated information based ONLY on what you've said before
- Real-time feedback about whether you're sharing new information

**Live Notes (Scratchpad)**
- As you talk, the AI builds "Live Notes" capturing your key points
- Displayed on the side as the conversation progresses
- Shows what the AI has understood so far
- Updated after each message
- These notes feed into your final analysis document

**Conversation Limits**
- Conversations auto-advance when you hit the follow-up limit for a question
- Conversations auto-advance when you repeat yourself too many times (no-new-info limit)
- Hard limit of 15 total messages per conversation
- Can manually stop the conversation any time with "Stop Conversation" button
- Stopping generates your final analysis immediately

**Final Analysis Document**
- When conversation ends, AI synthesizes all your Live Notes into a polished document
- Captures your full perspective with nuance, sentiment, uncertainty, and contradictions
- Displayed on your conversation page
- Used by moderator to synthesize across all participants

**Progress Tracking**
- See how many follow-ups remain for the current question
- See how many "no new information" responses remain before auto-advance
- Clear messaging when limits are reached
- Informed when conversation ends and why

### 1.3 Integrated Grader (Discussion Pre-Gate)

This feature was added recently to collect participant scores BEFORE they enter the main discussion.

**Moderator Setup**
- Separate grader question builder in the moderator dashboard
- Appears BEFORE the discussion questions section
- AI-powered grader prompt suggestions (optimized for scoring/evaluation prompts)
- Questions ask participants to score from 1-10 and explain their reasoning
- Reorderable, editable list just like discussion questions

**Participant Flow**
- When a session has grader questions, participants MUST complete the grader first
- Entry URL redirects to grader form if not yet submitted
- Grader form shows all prompts with score inputs (1-10) and reason textareas
- Optional "Additional Comments" field at the bottom
- After submitting, participants are redirected to the main discussion

**Grader Analysis**
- View grader responses in the moderator dashboard summary card
- Download CSV with all grader responses (scores, reasons, additional comments)
- CSV has columns: User ID, Q1 Score, Q1 Reason, Q2 Score, Q2 Reason, etc.

---

## 2. AI-AI Deliberation

Pure AI debate mode where multiple AI agents with different personas discuss a topic.

### 2.1 Moderator Features

**AI Session Management**
- Create AI-only deliberation sessions separate from human-AI sessions
- Define topic, description, and objective questions
- Configure multiple AI personas (agent descriptions)
- Each persona represents a different perspective or expertise
- Custom system prompt template with placeholders for persona, question, and opinions

**Question and Persona Setup**
- Define ordered list of questions (same builder as human-AI mode)
- Define list of personas (text descriptions of AI agents)
- AI suggestions available for questions
- Manual editing and reordering for both

**Knowledge Base (RAG)**
- Same as human-AI mode
- Upload documents or paste text
- Helps AI agents give informed opinions grounded in provided context

**Running Deliberations**
- Click "Run Deliberation" to start the AI debate
- System runs asynchronously in the background
- Opens transcript page to watch progress in real-time

### 2.2 AI Debate Mechanics

**Multi-Round Structure**
- For each question, all personas participate in two rounds:
  - **Round 1 (Initial)**: Each agent shares initial opinion
  - **Round 2 (Critique)**: Each agent sees others' opinions and responds/critiques
- Moves through all questions sequentially

**Transcript Capture**
- Full debate transcript saved to database
- Each turn records: question, persona, opinion/content, round/stage
- Organized by question for easy review

**Live Transcript Display**
- Transcript page shows debate organized by question
- Within each question: initial responses first, then critiques
- Color-coded by persona for readability
- Updates live as debate progresses (if refreshed)

**Final Summary**
- After debate completes, moderator can click "Generate Summary"
- AI synthesizes the full debate into a structured markdown summary
- Identifies consensus, disagreements, key arguments, and conclusions
- Summary saved and displayed on transcript page

---

## 3. Standalone Grader System

Pure evaluation mode separate from discussions. Participants score features/prompts.

### 3.1 Moderator Features

**Grader Session Management**
- Create grader sessions with unique IDs
- Define topic and detailed description (supports markdown)
- Build list of grading prompts (questions asking for 1-10 scores)
- AI-powered suggestions for grading prompts
- Activate one session at a time

**Knowledge Base (RAG)**
- Same as other modes
- Upload reference documents to inform AI suggestions
- Helps generate contextually relevant grading prompts

**Analysis Engine**
- Click "Analyze" after collecting responses
- System computes average score per question across all participants
- AI reads all reasons for each question and generates a summary (3-6 sentences)
- Final report shows:
  - Each question with average score
  - AI-generated summary of common themes in participant feedback
- Analysis saved as markdown in the session

**CSV Export**
- Download all grader responses as CSV
- Columns: User ID, Q1 Score, Q1 Reason, Q2 Score, Q2 Reason, etc., Additional Comments
- Easy import to Excel/Google Sheets for further analysis

### 3.2 Participant Features

**Grader Interface**
- View session topic and description (markdown-rendered)
- For each grading prompt:
  - Score input (1-10 scale)
  - Reason textarea (explain your score)
- Additional comments field (optional)
- Submit button saves responses

**Response Persistence**
- One response per user per session (enforced by database constraint)
- Responses can be updated by submitting again
- Pre-fills existing scores/reasons when revisiting

---

## 4. Cross-Cutting Features

These features work across all modes.

### 4.1 AI Integration

**OpenAI API**
- Uses GPT-4o-mini for all chat completions
- Uses text-embedding-3-small for knowledge base embeddings
- Centralized client configuration (single cached instance)
- Configurable model names via environment variables

**Structured JSON Responses**
- All AI responses return strict JSON for reliable parsing
- User bot returns: reply, breakdown, clarifications, new_information flag, notes, reasoning
- Moderator bot returns: internal reasoning (temp) and structured summary
- AI-AI agents return: formatted opinions per round

**Token Management**
- Estimates token usage before API calls
- Truncates conversation history to fit within limits
- Keeps last 8 turns of chat history in context
- Includes RAG chunks, prompts, and scratchpad within token budget

### 4.2 RAG (Knowledge Base)

**Text Processing**
- Supports .txt and .csv file uploads
- CSV files parsed into readable lines
- Text chunked into ~500-character segments with 50-character overlap
- Chunks embedded using OpenAI embeddings

**Vector Storage**
- Each session gets its own Chromadb collection (named "session-{id}")
- Embeddings stored in database with pgvector (PostgreSQL)
- Supports semantic search across chunks

**Retrieval**
- During conversation, user messages trigger semantic search
- Top 4 most relevant chunks retrieved
- Chunks injected into AI context with relevance scores
- Helps ground AI responses in provided materials

**Index Management**
- Rebuild index any time with new content
- Tracks chunk count and last build timestamp
- Reset collection when rebuilding

### 4.3 Centralized Prompts

**Prompt Package** (`prompts/prompts.py`)
- All system prompts defined in one place
- Documented with usage context
- Prompts for user bot personality, reasoning, output format, final analysis
- Prompts for moderator synthesis structure
- Easy to modify behavior application-wide

**Customization**
- Moderators can override default prompts per session
- Custom prompts stored in database
- Falls back to defaults if not specified

### 4.4 Session State Management

**Active Session Pattern**
- Each mode tracks one "active" session at a time
- Activating a session deactivates all others in that mode
- Participants automatically join the active session
- Prevents confusion about which session is current

**Database Models**
- DiscussionSession: human-AI mode sessions
- AIDeliberationSession: AI-AI mode sessions
- GraderSession: standalone grader sessions
- UserConversation: tracks each participant's state in human-AI mode
- Various response models: GraderResponse, DiscussionGraderResponse

**State Tracking**
- Conversation history stored as JSON array
- Current question index, follow-up count, no-new-info streak tracked
- Message count, active status, timestamps
- Scratchpad (temp.md) and final analysis (views_markdown) stored per participant

### 4.5 Data Export

**CSV Generation**
- Grader responses exported as CSV with proper formatting
- Integrated grader (discussion pre-gate) also exports CSV
- Headers dynamically generated based on questions
- Proper escaping for Excel/Sheets compatibility

---

## 5. Technical Infrastructure

### 5.1 Web Framework

**Django 5.1.2**
- Python web framework handling all backend logic
- PostgreSQL database (Neon in production, SQLite for local dev)
- Django templates for frontend rendering
- Bootstrap 5 for UI components

### 5.2 Deployment

**Render Hosting**
- Automatic deployment from GitHub
- PostgreSQL database provisioned
- Environment variables configured via dashboard
- Gunicorn + Uvicorn for ASGI server

**Environment Configuration**
- `OPENAI_API_KEY`: required for AI features
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Django security key
- Model names configurable for testing different OpenAI models

### 5.3 Development Workflow

**Local Setup**
- `run.sh` script handles setup and server start
- Virtual environment with all dependencies
- Django migrations applied automatically
- Development server at localhost:8000

**Access Patterns**
- Participant ID 0 always goes to moderator dashboard
- Participant IDs 1+ go to participant interfaces
- URL routing determines which mode (human-AI vs AI-AI vs grader)

---

## 6. Conversation Flow Mechanics

### 6.1 Novelty Detection

**Key Innovation**
- AI compares each user response ONLY against what that user has said before
- Does NOT compare against general knowledge or AI's own knowledge
- Information is "new" if the user hasn't mentioned it in this conversation
- Tracks consecutive responses without new information

**Why This Matters**
- Prevents conversations from ending prematurely
- Allows common knowledge to count as "new" if user hasn't stated it yet
- Focuses on exhausting the user's perspective, not teaching the AI
- Powers the no-new-information limit for question advancement

### 6.2 Question Advancement

**Automatic Triggers**
- **Follow-up limit reached**: After X responses to a question, move to next
- **No-new-info limit reached**: After X consecutive non-novel responses, move to next
- **Last question completion**: If no questions remain, end conversation

**Manual Control**
- Moderator sets both limits when creating session
- Participants can manually stop any time
- System enforces 15-message hard cap

### 6.3 Live Notes vs Final Analysis

**Live Notes (temp.md / scratchpad)**
- Updated after EVERY message during conversation
- Bullet-point style capturing key points as they emerge
- Visible to participant in real-time
- Append-only (never rewritten)
- Raw, unpolished notes

**Final Analysis (views_markdown)**
- Generated ONLY when conversation ends
- Synthesizes all Live Notes into polished document
- Includes nuance, sentiment, uncertainty, contradictions
- Used by moderator for cross-participant synthesis
- Markdown formatted for readability

---

## 7. UI Components

### 7.1 Moderator Dashboard

**Session Selector**
- Dropdown showing all sessions (most recent first)
- Load button to switch between sessions
- Shows active session highlighted

**Session Form**
- Input fields for session ID, topic, description
- Text editor for knowledge base
- Custom prompt editors (collapsible sections)
- Save Changes / Save As New buttons
- Activate Session button

**Question Builders**
- Dynamic JavaScript builders for both discussion and grader questions
- "Generate Questions" button for AI suggestions
- Add question button
- Each question has up/down/remove buttons
- Questions reorder live

**Action Buttons**
- Run RAG (rebuild knowledge index)
- Analyze Responses (generate moderator synthesis)
- Run Deliberation (AI-AI mode only)

**Display Panels**
- RAG index info (chunk count, last built time)
- Moderator analysis display (markdown-rendered)
- List of participant conversations with status
- Grader summary and CSV download link (if applicable)

### 7.2 Participant Interface

**Chat Window**
- Message history displayed chronologically
- User messages and AI responses clearly differentiated
- Auto-scroll to latest message

**Input Area**
- Text input for participant responses
- Submit button (disabled when conversation inactive)
- Stop Conversation button (visible when active)

**Context Sidebar**
- Session topic and current question displayed
- Question progress (e.g., "Question 2 of 5")
- Next question preview
- Follow-up limit progress bar
- No-new-info limit progress bar
- Live Notes displayed (updated live)
- Final Analysis displayed (when conversation ends)

**Status Messages**
- Django messages framework for feedback
- Success, error, warning, info messages
- Clear indication of why conversation ended

### 7.3 Grader Interface

**Form Layout**
- Session description at top (markdown-rendered)
- Each question in sequence:
  - Question number and text
  - Score input (1-10, number type with validation)
  - Reason textarea (required)
- Additional comments textarea (optional)
- Submit button

**Validation**
- Client-side HTML5 validation (required fields, number range)
- Server-side validation
- Error messages for invalid inputs

---

## 8. API Endpoints

### 8.1 Internal APIs

**Question Generation API** (`/generate-questions/`)
- POST endpoint
- Takes: topic, question_type (discussion vs grader), existing questions, knowledge_base
- Returns: JSON with 4 suggested questions
- Used by all question builders

**Session Creation API** (`/create-session/`)
- POST endpoint
- Takes: s_id, topic
- Creates new session and returns session ID
- Used by modal forms in dashboards

### 8.2 View Routes

**Human-AI Mode**
- `/`: System choice page
- `/entry/`: Participant ID entry
- `/entry/<id>/`: Participant conversation page
- `/entry/0/` → redirects to `/human/moderator/`
- `/human/moderator/`: Moderator dashboard

**AI-AI Mode**
- `/ai/`: AI deliberation entry
- `/ai/moderator/`: AI moderator dashboard
- `/ai/results/<run_id>/`: Transcript and summary page

**Grader Mode**
- `/grader/`: Grader entry
- `/grader/moderator/`: Grader moderator dashboard
- `/grader/user/<id>/`: Grader participant form
- `/grader/export/<session_id>/`: CSV download

**Discussion Grader (Integrated)**
- `/discussion/grader/<user_id>/`: Integrated grader form (before discussion)
- `/discussion/grader/export/<session_id>/`: CSV download for integrated responses

---

## 9. Data Models

### 9.1 Human-AI Mode

**DiscussionSession**
- Session configuration: s_id, topic, description
- Question lists: objective_questions, grader_objective_questions (JSON arrays)
- Limits: question_followup_limit, no_new_information_limit
- Prompts: user_system_prompt, moderator_system_prompt
- Knowledge base: knowledge_base (text), rag_chunk_count, rag_last_built_at
- Analysis: moderator_temp, moderator_summary
- Status: is_active, created_at, updated_at

**UserConversation**
- Links to session and user_id
- State: history (JSON), scratchpad, views_markdown
- Tracking: message_count, consecutive_no_new, question_followups, current_question_index
- Status: active, created_at, updated_at
- Constraint: unique (session, user_id)

**DiscussionGraderResponse**
- Links to session and user_id
- Data: scores (JSON array), reasons (JSON array), additional_comments
- Timestamp: submitted_at
- Constraint: unique (session, user_id)

### 9.2 AI-AI Mode

**AIDeliberationSession**
- Session config: s_id, topic, description
- Questions and personas: objective_questions (JSON), personas (JSON)
- Prompt: system_prompt_template
- Status: is_active, created_at, updated_at

**AIDebateRun**
- Links to session
- Data: transcript (JSON array of turns)
- Status: completed, created_at, updated_at

**AIDebateSummary**
- Links to session (one-to-one)
- Summary: summary_markdown
- Metadata: topic, description, objective_questions, personas
- Timestamp: created_at, updated_at

### 9.3 Grader Mode

**GraderSession**
- Session config: s_id, topic, description
- Questions: objective_questions (JSON array)
- Knowledge base: knowledge_base, rag_chunk_count, rag_last_built_at
- Analysis: analysis_markdown
- Status: is_active, created_at, updated_at

**GraderResponse**
- Links to session and user_id
- Data: scores (JSON), reasons (JSON), additional_comments
- Timestamp: submitted_at
- Constraint: unique (session, user_id)

---

## 10. Recent Additions

These features were added in the most recent development phase:

### 10.1 Integrated Grader

- Grader questions added to DiscussionSession model
- Separate question builder in moderator dashboard for grader prompts
- Participant flow now gates discussion entry on grader completion
- If session has grader questions, participants must complete grader first
- After grader submission, redirected to main discussion
- CSV export for grader responses integrated into moderator dashboard
- AI suggestions for grader prompts (optimized for scoring/evaluation language)

### 10.2 Question Type Awareness

- Question generation API now accepts `question_type` parameter
- Different prompts for discussion vs grader question generation
- Grader prompts focus on scoring/evaluation language (1-10 scale)
- Discussion prompts focus on open-ended objective questions

### 10.3 UI Improvements

- Grader prompts reordered to appear BEFORE discussion questions in moderator dashboard
- CSV download link moved to summary card for visibility
- Button labels clarified ("Go to Discussion" instead of "Return to discussion")
- Question builder JavaScript refactored into reusable function
- Support for both discussion and grader builders on same page

---

## Summary

DiscussChat provides three deliberation modes:
1. **Human-AI**: Structured discussions with AI facilitation, question flow, novelty tracking
2. **AI-AI**: Pure AI debates with multiple personas across questions
3. **Grader**: Score-based evaluation system with AI-powered analysis

Key capabilities:
- AI-powered question suggestions
- Knowledge base integration (RAG) for informed responses
- Customizable AI prompts per session
- Structured conversation flow with automatic question advancement
- Real-time live notes and final analysis synthesis
- Moderator synthesis across all participants
- CSV export for quantitative analysis
- Integrated grader to collect scores before discussions

All modes share common infrastructure: OpenAI integration, RAG system, centralized prompts, session management, and data export capabilities.
