# DiscussChat - AI-Facilitated Topic Discussion Platform

DiscussChat is a web-based platform that uses artificial intelligence to help people have structured discussions on various topics. It allows moderators to set up discussion sessions, and participants to share their views while an AI assistant guides the conversation, draws from provided knowledge, and helps synthesize everyone's perspectives into a comprehensive summary.

## Architecture

DiscussChat is built as a web application using Django, a popular framework for creating websites with Python. Here's how the system works at a high level:

### Technology Stack

- **Backend Framework**: Django (Python web framework)
- **Database**: PostgreSQL (via Neon for production) or SQLite (for local development)
- **AI Provider**: OpenAI API (GPT-4o-mini for conversations, text-embedding-3-small for RAG)
- **Frontend**: Django templates with HTML/CSS/JavaScript
- **Deployment**: Render (web hosting platform)

### System Components

The platform consists of several key parts that work together:

#### 1. Web Interface

A user-friendly website where moderators and participants interact:
- **Moderator Dashboard** (`/entry/0`): Control center for creating sessions, managing questions, uploading knowledge bases, configuring AI prompts, and viewing synthesis results
- **Participant Chat Interface** (`/entry/{user_id}`): Simple conversational interface where participants answer questions and share their perspectives
- **Entry System**: URL-based access control using participant IDs (0 for moderator, 1+ for participants)

#### 2. AI Conversation System

Powered by OpenAI's language models, the AI acts as a conversation facilitator with distinct roles:

**User-Facing Bot**:
- Asks thoughtful questions based on the moderator's objective question list
- Detects when new information is shared by comparing responses ONLY against what the user has previously stated (not against the AI's general knowledge)
- Maintains a "scratchpad" (Live Notes) tracking all user input in real-time
- Automatically advances through questions based on the follow-up limit
- Generates a final analysis document (views_markdown) when the conversation ends
- Uses the moderator-defined limit for consecutive responses without new information to auto-advance (or close the final question) while still enforcing the 15-message cap

**Moderator Synthesis Bot**:
- Analyzes all participants' final analysis documents after conversations complete
- Produces structured synthesis identifying:
  - Consensus points (areas of agreement)
  - Disagreement points (divergent perspectives)
  - Strength of sentiment (emotional intensity indicators)
  - Confusion areas (unclear or ambiguous topics)
  - Missing information (gaps in coverage)
- Maintains internal reasoning (moderator_temp) for transparency

#### 3. Knowledge Base Integration (RAG System)

Moderators can provide background information or documents:
- **Upload Process**: Documents are uploaded via the moderator dashboard
- **Embedding Generation**: Text is chunked and embedded using OpenAI's text-embedding-3-small model
- **Vector Storage**: Embeddings are stored in the database (using pgvector for PostgreSQL)
- **Retrieval**: During conversations, user messages trigger semantic search to find relevant document chunks
- **Context Injection**: Retrieved chunks are injected into the AI's context with relevance scores
- **Purpose**: Helps the AI provide more informed and contextually accurate responses

#### 4. Database Storage

All discussion data is stored in a relational database with the following key models:

**DiscussionSession**:
- Topic and description
- Knowledge base (uploaded documents for RAG)
- Objective questions (ordered list)
- Question follow-up limit (how many responses per question)
- No-new-information limit (how many consecutive responses without new content trigger an advance or closure)
- Custom AI prompts (user_system_prompt, moderator_system_prompt)
- Synthesis results (moderator_temp, moderator_summary)

**UserConversation**:
- Participant ID linkage to the session
- Chat history (JSON array of message turns)
- Scratchpad/Live Notes (temp.md - accumulated notes during conversation)
- Final analysis (views_markdown - synthesized perspective document)
- Question tracking (current_question_index, question_followups)
- State flags (active status, consecutive_no_new counter, message_count)

#### 5. Prompt System

Centralized prompt management in `prompts/prompts.py`:
- **USER_BOT_BASE_PROMPT**: Establishes bot personality (investigative reporter)
- **USER_BOT_REASONING_PROMPT**: Instructs structured analysis and novelty detection
- **USER_BOT_OUTPUT_INSTRUCTIONS**: Defines JSON response format
- **USER_BOT_FINAL_PROMPT**: Guides final analysis synthesis
- **MODERATOR_ANALYSIS_PROMPT**: Instructs multi-perspective synthesis
- **Customization**: Moderators can override defaults per-session via the dashboard

### Data Flow & Conversation Lifecycle

#### Phase 1: Session Setup

1. Moderator creates a new discussion session with:
   - Topic and optional description
   - Optional knowledge base upload (for RAG)
   - Optional custom AI prompts
2. System stores session configuration in database
3. If knowledge base provided, system:
   - Chunks the document
   - Generates embeddings
   - Stores vectors in database

#### Phase 2: Question Configuration

1. Moderator uses "Generate Questions" feature:
   - AI analyzes topic and knowledge base
   - Proposes 4 objective questions
   - Moderator reviews suggestions
2. Moderator builds final question list:
   - Accepts AI suggestions (any or all)
   - Adds custom questions
   - Arranges in preferred order
   - Sets follow-up limit (responses per question)
3. System stores ordered question sequence

#### Phase 3: Participant Conversations

1. Participant accesses chat interface via unique URL
2. System initializes UserConversation record
3. For each user message:
   - **RAG Retrieval**: Semantic search finds relevant knowledge chunks
   - **Context Building**: System assembles:
     - System prompts (personality + reasoning instructions)
     - Question plan and current question
     - Conversation history (last 8 turns)
     - Live Notes (scratchpad) from previous turns
     - RAG context (retrieved document chunks)
     - Novelty tracking state
   - **AI Processing**: OpenAI generates structured JSON response:
     - assistant_reply (what to say to user)
     - breakdown (bullet points of user's message)
     - clarification_requests (follow-up questions)
     - new_information (boolean - is this new from user?)
     - temp_md_entry (notes to append to scratchpad)
     - reasoning_notes (justification for novelty decision)
   - **State Updates**:
     - Append to chat history
     - Update scratchpad with temp_md_entry
     - Increment message counter
     - Track consecutive_no_new counter
     - Track question_followups counter
4. **Question Advancement**:
   - When the follow-up limit for a question is reached, advance to the next question; if none remain, close the conversation
   - When the no-new-information limit for a question is reached, advance to the next question; if none remain, close the conversation
   - When all questions are exhausted through moderator actions or limits, the assistant wraps up and ends the session
5. **Conversation Termination** (automatic or manual):
   - After 15 total messages
   - Manual stop by participant
   - Completion of the final question via limits or participant decisions
6. **Final Analysis Generation**:
   - AI reviews complete scratchpad
   - Generates polished views_markdown document
   - Captures nuance, sentiment, contradictions

#### Phase 4: Moderator Synthesis

1. Moderator requests synthesis analysis
2. System collects all participants' views_markdown documents
3. Moderator bot processes:
   - Reads each participant's final analysis
   - Maintains internal reasoning (moderator_temp)
   - Cross-compares perspectives
4. System generates structured summary:
   - Consensus areas
   - Disagreement points
   - Sentiment strength indicators
   - Confusion/ambiguity areas
   - Information gaps
5. Results stored and displayed in dashboard

### Key Design Decisions

**No Participant Limits**: Participants can join at any time; all follow the same question sequence

**Question-Driven Flow**: Structured progression through ordered questions ensures focused conversations

**Novelty Detection**: AI tracks what each user has said (not general knowledge) and applies the moderator-defined no-new-information limit to decide when to advance questions or close the discussion

**Dual-Document System**: 
- Scratchpad (temp.md): Real-time notes during conversation
- Final Analysis (views_markdown): Polished synthesis at conversation end

**RAG Integration**: Optional knowledge base ensures AI responses are grounded in provided context

**Customizable Prompts**: Per-session AI behavior customization for different discussion styles

**Multi-Stage Synthesis**: Individual analysis → Cross-participant synthesis → Structured insights

## Creating a database on Neondb

- Create an account. You will land on the dashboard.
- Select "Create Project".
![alt text](screenshots/create-project.png)
- Enter the project details in the next screen and click "Create".
![alt text](screenshots/create-project.png)
- Click on "Connect" in the top right corner of the Dashboard.
![alt text](screenshots/dashboard.png)
- Now you can see the connection string. That will be the value of the `DATABASE_URL` environment variable.
![alt text](screenshots/connection_string.png)
   
## Running the application

To run DiscussChat on your computer, follow these steps:

1. **Clone the project**: Download the code from the repository.
   ```bash
   git clone https://github.com/the-blue-fountain/ai-deliberation-service.git
   cd ai-deliberation-service
   ```

2. **Make the setup script executable**: This allows you to run the installation script.
   ```bash
   chmod +x run.sh
   ```

3. **Run the setup script**: This will install the necessary tools and dependencies and run the application on localhost.
   ```bash
   ./run.sh
   ```

6. **Access the application**: Open your web browser and go to `http://localhost:8000/`. Use participant ID `0` for the moderator dashboard, or `1`, `2`, `3`, etc. for participants.

## Deploying to Render

### Quick Deploy with Blueprint

This project includes a `render.yaml` blueprint for one-click deployment:

1. **Fork or clone** this repository to your GitHub account
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click **"New"** → **"Blueprint"**
4. Connect your GitHub repository
5. Render will automatically:
   - Create a PostgreSQL database
   - Deploy the web service
   - Configure environment variables
   - Run migrations

### Manual Deployment Steps

If you prefer manual setup:

#### 1. Create PostgreSQL Database

- In Render Dashboard, click **"New"** → **"PostgreSQL"**
- Choose a name (e.g., `ai-deliberation-db`)
- Select the **Free** plan
- Click **"Create Database"**
- Save the **Internal Database URL** (you'll need this later)

#### 2. Create Web Service

- Click **"New"** → **"Web Service"**
- Connect your GitHub repository
- Configure the service:
  - **Name**: `ai-deliberation-service`
  - **Runtime**: `Python 3`
  - **Build Command**: `./build.sh`
  - **Start Command**: `cd chatbot_site && python -m gunicorn chatbot_site.asgi:application -k uvicorn.workers.UvicornWorker`

#### 3. Configure Environment Variables

Add these environment variables in Render Dashboard:

**Required:**
- `DATABASE_URL`: Use the Internal Database URL from step 1
- `SECRET_KEY`: Click "Generate" to create a secure random value
- `OPENAI_API_KEY`: Your OpenAI API key

**Optional:**
- `OPENAI_MODEL_NAME`: `gpt-4o-mini` (default)
- `OPENAI_EMBEDDING_MODEL`: `text-embedding-3-small` (default)
- `WEB_CONCURRENCY`: `4` (number of worker processes)

**Important:** Render automatically sets `RENDER_EXTERNAL_HOSTNAME` - you don't need to configure this manually.

#### 4. Deploy

- Click **"Create Web Service"**
- Render will automatically:
  - Install dependencies
  - Run database migrations
  - Collect static files
  - Start the application

### Understanding Render Configuration

The application is configured to work seamlessly with Render:

**Debug Mode**: Automatically disabled when `RENDER` environment variable is present (set by Render automatically)

**Allowed Hosts**: Automatically includes `RENDER_EXTERNAL_HOSTNAME` for your `*.onrender.com` domain

**Database**: Configured with SSL required for PostgreSQL connections

**Static Files**: Collected during build and served via WhiteNoise (if configured) or Render's CDN

### Post-Deployment

After deployment:

1. Access your app at `https://your-service-name.onrender.com`
2. Create discussion sessions via the moderator dashboard (participant ID: 0)
3. Share participant links (participant IDs: 1, 2, 3, etc.)

### Troubleshooting Render Deployment

**Build Fails:**
- Check that `build.sh` is executable (`chmod +x build.sh`)
- Verify all dependencies are in `requirements.txt`
- Check build logs in Render Dashboard

**Application Won't Start:**
- Verify `DATABASE_URL` is set correctly
- Check that `SECRET_KEY` is configured
- Review application logs in Render Dashboard

**Database Connection Issues:**
- Ensure you're using the **Internal Database URL** (not External)
- Verify SSL is enabled in database settings
- Check that database and web service are in the same region

**Static Files Not Loading:**
- Verify `STATIC_ROOT` is configured in settings
- Check that `collectstatic` ran during build
- Review static file paths in templates

### Environment Variables Reference

Render automatically provides these variables:
- `RENDER`: Indicates running on Render (used to set DEBUG=False)
- `RENDER_EXTERNAL_HOSTNAME`: Your app's hostname (e.g., `myapp.onrender.com`)
- `PORT`: The port your app should listen on (handled by gunicorn)

You must configure:
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Django secret key (use "Generate" button)
- `OPENAI_API_KEY`: Your OpenAI API key

## Environment Variables Reference

### Local Development (.env.local)

```env
# OpenAI Configuration (Required)
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL_NAME=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database (Optional - uses SQLite if not set)
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

### Production (Render)

Render automatically provides:
- `RENDER` - Indicates production environment (sets DEBUG=False)
- `RENDER_EXTERNAL_HOSTNAME` - Your app's domain (automatically added to ALLOWED_HOSTS)
- `PORT` - Application port (handled by gunicorn)

You must configure in Render Dashboard:
- `DATABASE_URL` - PostgreSQL connection string (from Render database)
- `SECRET_KEY` - Django secret key (use "Generate" button)
- `OPENAI_API_KEY` - Your OpenAI API key

Optional production variables:
- `OPENAI_MODEL_NAME` - Default: `gpt-4o-mini`
- `OPENAI_EMBEDDING_MODEL` - Default: `text-embedding-3-small`
- `WEB_CONCURRENCY` - Number of worker processes (default: 4)
- `ALLOWED_HOSTS` - Additional comma-separated domains
- `DJANGO_CSRF_TRUSTED_ORIGINS` - Trusted origins for CSRF (comma-separated)

## Supported OS

DiscussChat has first-class support for Linux systems. It is designed and tested primarily on Linux, ensuring the best performance and compatibility. While it may work on other operating systems, Linux is recommended for the most reliable experience.
