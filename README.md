# DiscussChat - AI-Facilitated Topic Discussion Platform

A sophisticated Django-based platform that uses AI to facilitate structured discussions on topics, capturing nuanced perspectives from multiple participants with RAG-enhanced context awareness.

## 🎯 Overview

DiscussChat enables moderators to:
- Define topics for discussion
- Set custom AI prompts (or use defaults)
- Upload knowledge bases for context-aware responses
- Host conversations with multiple users simultaneously
- Synthesize participant perspectives into comprehensive cross-user analysis

Each **user** benefits from:
- Intelligent follow-up questions
- Detection of new information vs. repetition
- Live documentation of evolving perspectives
- Respectful, in-depth exploration of their views
- RAG-enhanced context from the moderator's knowledge base

## 🏗️ Architecture

### Core Components

#### **Models** (`core/models.py`)
- **DiscussionSession**: Manages a complete discussion workflow
  - Topic definition
  - Knowledge base (for RAG)
  - User and moderator system prompts (customizable)
  - RAG index metadata
  - Moderator analysis outputs
  
- **UserConversation**: Tracks each user within a session
  - Conversation history (JSON)
  - Live notes (scratchpad during discussion)
  - Final analysis (synthesized perspective)
  - Message count and engagement tracking

#### **Services** (`core/services/`)
- **conversation_service.py**: 
  - `UserConversationService`: Manages individual user conversations
  - `ModeratorAnalysisService`: Synthesizes cross-user perspectives
  - Token limiting to prevent API overages
  
- **rag_service.py**: 
  - Builds and queries in-memory vector indexes
  - Uses Chroma for vector storage
  - Embeds documents with OpenAI's text-embedding-3-small model
  
- **openai_client.py**: 
  - Centralized OpenAI API client
  - Reads API key from environment or local file

#### **Views** (`core/views.py`)
- **entry_point**: Participant ID selection
- **moderator_dashboard**: Session management and analysis
- **user_conversation**: Live discussion interface

#### **Prompts** (`prompts/prompts.py`)
All system prompts are centralized with detailed documentation of their roles:
- `USER_BOT_BASE_PROMPT`: Defines the AI's personality and interaction style
- `USER_BOT_REASONING_PROMPT`: Instructs internal chain-of-thought analysis
- `USER_BOT_OUTPUT_INSTRUCTIONS`: Specifies JSON response structure
- `USER_BOT_FINAL_PROMPT`: Guides synthesis of live notes into final analysis
- `DEFAULT_MODERATOR_SYSTEM_PROMPT`: Defines moderator synthesis behavior

### Data Flow

```
Moderator Creates Session
    ↓
[Sets topic, knowledge base, custom prompts]
    ↓
Activate Session → Users Join (any number)
    ↓
[Each user has independent conversation]
    ↓
User messages → RAG retrieval → AI response → Live notes accumulation
    ↓
Conversation ends (manual stop or 15-message limit)
    ↓
User's live notes → Synthesized into Final Analysis
    ↓
[Moderator clicks "Analyze"]
    ↓
All user analyses → Cross-user synthesis → Moderator summary
    ↓
Results displayed with interactive formatting
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL (Neon recommended for hosting)
- OpenAI API key
- Virtual environment

### Local Development

1. **Set up environment**
```bash
cd chatbot-nodiv/chatbot_site
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure database**
```bash
# Local SQLite (default) or set DATABASE_URL for PostgreSQL
export DATABASE_URL="postgresql://user:password@host/dbname?sslmode=require"
```

3. **Configure OpenAI API key**
```bash
# Option 1: Environment variable (preferred for production)
export OPENAI_API_KEY="sk-..."

# Option 2: Local file (for development)
echo "sk-..." > ../openai-api-key.txt
```

4. **Initialize database**
```bash
python manage.py migrate
python manage.py runserver
```

5. **Access the application**
- Visit `http://localhost:8000/`
- Moderator dashboard: Enter participant ID `0`
- User conversation: Enter participant ID `1, 2, 3, ...`

## 📊 Usage

### Moderator Workflow

1. **Create Session**
   - Click "Save As New" in Moderator Controls
   - Enter unique session ID, topic, knowledge base
   - Optionally customize AI prompts

2. **Activate Session**
   - Select the session from the dropdown
   - Click "Activate Session" (sets it as active for users)

3. **Build RAG Index**
   - Click "Run RAG" to index the knowledge base
   - System builds vector embeddings and chunks
   - Indices live in memory (rebuild after server restart)

4. **Monitor Conversations**
   - "User Conversations" section shows active participants
   - See message counts and completion status

5. **Analyze Results**
   - Once users finish conversations, click "Analyze"
   - System synthesizes all perspectives into a structured summary
   - Results displayed with color-coded sections:
     - ✓ **Consensus** (green) - areas of agreement
     - ⚠ **Disagreement** (yellow) - points of divergence
     - 💭 **Sentiment Strength** (blue) - emotional intensity
     - ❓ **Confusion/Gaps** (red) - unclear areas
     - 📋 **Missing Information** (gray) - gaps in coverage

### User Workflow

1. **Enter Participant ID**
   - Choose a unique numeric ID (1, 2, 3, etc.)
   - Join the active session

2. **View Session Context**
   - Topic defined by moderator
   - RAG knowledge base context available
   - Knowledge base is accessible if moderator ran RAG

3. **Share Your Perspective**
   - Type your response and click "Send"
   - AI provides:
     - Thoughtful follow-up questions
     - Clarification requests if needed
     - Internal breakdown of your response
   - Your perspective accumulates in "Live Notes"

4. **Stop Conversation**
   - When done, click "Stop Conversation"
   - Live notes synthesized into "Final Analysis"
   - Analysis preserved for moderator synthesis

## 🧠 Key Features

### Intelligent Conversation Flow
- **New Information Detection**: Tracks whether responses add new knowledge or repeat prior points
- **Streak Counting**: Detects when users have exhausted their input (2+ consecutive responses without new information)
- **Message Limiting**: Automatic stop at 15 messages per user
- **Clarification Requests**: AI asks targeted questions to dig deeper

### RAG Integration
- **In-Memory Indexing**: Vector indexes live during the session, rebuild via "Run RAG" if needed
- **Semantic Search**: Retrieves most relevant knowledge base chunks for each user query
- **Metadata Tracking**: Preserves chunk indices for debugging and traceability

### Token Management
- **Automatic Truncation**: Truncates conversation history if token count exceeds 8,000
- **Safe Limits**: Prevents API errors from oversized requests
- **Estimation**: ~1 token per 4 characters for conservative safety

### JSON-Based Architecture
- **User Bot Output**: Structured JSON with reply, breakdown, new_information flag, and reasoning
- **Moderator Synthesis**: Structured JSON with consensus, disagreement, sentiment, confusion, and missing information
- **Easy Integration**: JSON structure enables seamless backend processing and template rendering

### Multi-Session Management
- **Session Persistence**: All data stored in PostgreSQL (Neon in production)
- **Active Session Switching**: Only one session is "active" at a time for new users
- **Historical Data**: Previous sessions remain available for review and re-analysis

## 🗄️ Database Schema

### core_discussionsession
| Field | Type | Purpose |
|-------|------|---------|
| id | BigInt | Primary key |
| s_id | CharField | Unique session identifier |
| topic | CharField | Discussion topic |
| knowledge_base | Text | Moderator-provided context |
| user_system_prompt | Text | Custom or default user bot prompt |
| moderator_system_prompt | Text | Custom or default moderator bot prompt |
| rag_chunk_count | Integer | Number of indexed chunks |
| rag_last_built_at | DateTime | Last RAG rebuild timestamp |
| moderator_temp | Text | Moderator's step-by-step reasoning (JSON) |
| moderator_summary | Text | Final synthesis (JSON) |
| is_active | Boolean | Whether this is the active session |
| created_at / updated_at | DateTime | Timestamps |

### core_userconversation
| Field | Type | Purpose |
|-------|------|---------|
| id | BigInt | Primary key |
| session_id | BigInt | FK to DiscussionSession |
| user_id | Integer | Participant identifier |
| history | JSON | Chat history [{role, content}, ...] |
| scratchpad | Text | Live notes during conversation |
| views_markdown | Text | Final analysis document |
| message_count | Integer | Number of user messages |
| consecutive_no_new | Integer | Consecutive responses without new info |
| active | Boolean | Whether conversation is ongoing |
| created_at / updated_at | DateTime | Timestamps |

## ⚙️ Configuration

### Environment Variables
```bash
DJANGO_DEBUG=True                              # Debug mode (set to False for production)
DATABASE_URL="postgresql://..."                # PostgreSQL connection (optional; SQLite is default)
OPENAI_API_KEY="sk-..."                       # OpenAI API key
DJANGO_SECRET_KEY="..."                       # Django secret (auto-generated if missing)
DJANGO_CSRF_TRUSTED_ORIGINS="https://..."     # CSRF origins for production
```

### Settings
Key settings in `chatbot_site/settings.py`:
- `OPENAI_MODEL_NAME`: Model used for all AI interactions (default: `gpt-4o-mini`)
- `OPENAI_EMBEDDING_MODEL`: Embedding model for RAG (default: `text-embedding-3-small`)
- `ALLOWED_HOSTS`: Host configuration (set to `['*']` for demo, restrict for production)

## 🔄 Conversation Lifecycle

1. **User sends message**
   - RAG retrieves relevant knowledge base chunks
   - Message combined with system prompts and history
   - Token count checked; history truncated if needed
   - OpenAI API called with JSON response format

2. **Bot responds with JSON**
   ```json
   {
     "assistant_reply": "...",
     "breakdown": ["point 1", "point 2"],
     "clarification_requests": ["question 1"],
     "new_information": true,
     "temp_md_entry": "- New point: ...",
     "reasoning_notes": "This adds..."
   }
   ```

3. **Response processed**
   - Live notes appended (without repetition)
   - Message count incremented
   - New information flag tracked
   - Consecutive streak managed

4. **Conversation ends** (manual or auto)
   - All live notes sent to OpenAI for synthesis
   - Final analysis generated and saved
   - User's views preserved for moderator synthesis

5. **Moderator analyzes** (all users done)
   - Collects all user final analyses
   - Sends to OpenAI with moderator synthesis prompt
   - Returns:
     - `moderator_temp`: Step-by-step reasoning
     - `moderator_summary`: Structured JSON with insights

## 📦 Deployment

### Render (Recommended for Production)

1. **Create Neon PostgreSQL database**
   - Add `DATABASE_URL` to Render environment

2. **Configure Render Service**
   ```yaml
   # render.yaml
   services:
     - type: web
       name: discusschat
       env: python
       buildCommand: pip install -r requirements.txt && python manage.py migrate
       startCommand: gunicorn chatbot_site.wsgi
       envVars:
         - key: DJANGO_DEBUG
           value: false
         - key: OPENAI_API_KEY
           sync: false  # Keep it secret!
   ```

3. **Deploy**
   ```bash
   git push origin main  # Trigger Render deployment
   ```

## 🛠️ Development

### Project Structure
```
chatbot-nodiv/
├── chatbot_site/              # Django project
│   ├── core/                  # Main app
│   │   ├── models.py          # DB models
│   │   ├── views.py           # View handlers
│   │   ├── forms.py           # Form definitions
│   │   ├── services/          # Business logic
│   │   │   ├── conversation_service.py
│   │   │   ├── rag_service.py
│   │   │   └── openai_client.py
│   │   ├── templatetags/      # Custom template filters
│   │   └── migrations/        # DB migrations
│   ├── templates/             # HTML templates
│   ├── static/                # CSS, JS
│   └── settings.py            # Django config
├── prompts/                   # Centralized prompts
│   └── prompts.py             # All system prompts
├── requirements.txt           # Python dependencies
└── manage.py                  # Django CLI
```

### Running Tests
```bash
python manage.py test core
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

## 🐛 Troubleshooting

### "RAG index is empty"
- **Cause**: Knowledge base not provided or RAG not rebuilt
- **Fix**: Add knowledge base content and click "Run RAG"

### "Unable to stop the conversation"
- **Cause**: OpenAI API error or invalid live notes
- **Fix**: Check API key, verify knowledge base format

### No consensus in moderator summary
- **Cause**: Not enough user conversations or differing views
- **Fix**: Ensure multiple users have submitted perspectives

### Token limit errors
- **Cause**: Very long conversation history + long user message
- **Fix**: Auto-truncation handles this; monitor API usage

## 📝 License

This project is maintained by [The Blue Fountain](https://github.com/the-blue-fountain).

## 🤝 Contributing

Contributions are welcome! Please submit issues or pull requests.

## 📧 Support

For questions or issues, please open a GitHub issue or contact the maintainers.

---

**Last Updated**: October 2025  
**Version**: 1.0.0
