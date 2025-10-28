# DiscussChat - AI-Facilitated Topic Discussion Platform

DiscussChat is a web-based platform that uses artificial intelligence to help people have structured discussions on various topics. It allows moderators to set up discussion sessions, and participants to share their views while an AI assistant guides the conversation, draws from provided knowledge, and helps synthesize everyone's perspectives into a comprehensive summary.

## Architecture

DiscussChat is built as a web application using Django, a popular framework for creating websites with Python. Here's how the system works at a high level:

### How the Platform is Structured

The platform consists of several key parts that work together:

1. **Web Interface**: A user-friendly website where moderators and participants interact. Moderators use a dashboard to set up and manage discussions, while participants have a simple chat interface.

2. **AI Assistant**: Powered by OpenAI's language models, the AI acts as a conversation facilitator. It asks thoughtful questions, detects when new information is shared, and helps explore participants' views in depth.

3. **Knowledge Base Integration**: Moderators can provide background information or documents related to the discussion topic. The AI uses this knowledge to give more informed and relevant responses.

4. **Database Storage**: All discussion data is stored in a database. This includes:
   - Discussion sessions: Details like the topic, any provided knowledge base, and custom instructions for the AI.
   - User conversations: Each participant's chat history, notes taken during the discussion, and a final summary of their views.
   - Analysis results: Synthesized insights from all participants, highlighting areas of agreement, disagreement, and gaps in understanding.

Important note: The platform no longer requires moderators to specify how many participants will join. Moderators provide a topic and an objective question (or use the "Generate Questions" helper) and the same question is presented to every participant. This makes it effortless to add participants at any time.

### How a Discussion Works

1. **Setup Phase**: A moderator creates a new discussion session by choosing a topic and optionally providing background information or custom instructions for the AI.

2. **Question generation & Participant Phase**: After creating a session, the moderator can press "Generate Questions" to ask the AI to propose four short, objective candidate questions based on the topic. The moderator selects one of those questions (or chooses "None of these" and types their own). That single objective question is then given to every participant. Participants can join at any time and will see the same question when they answer.

3. **Synthesis Phase**: Once participants finish sharing, the AI combines everyone's individual summaries into a comprehensive overview. This highlights common ground, differences of opinion, strong feelings, and areas that need more clarification.

The system is designed to handle multiple discussions at once and keeps all data organized so moderators can review past sessions or run new analyses.

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

## Creating an account on Render

- Go to [Render](https://render.com/) and sign up for an account.
![alt text](screenshots/create-account-render.png)
- Once logged in, select "New Web Service".
![alt text](screenshots/web-services.png)
- We chose to get the project from GitHub to create the web service. Enter the repo url and click "Connect".
![alt text](screenshots/create-web-service.png)
- In the enxt screen, you will be asked to fill several boxes, and most will be pre-filled. You will have to set the start an dbuild commands as in the below screenshot:
![alt text](screenshots/commands.png)
- For the enviroment variables, you can simply select "Add from .env".
![alt text](screenshots/env.png)
- Paste the contents of your `.env` file and click "Add variables".
![alt text](screenshots/env-add.png)

That's it!

## Environment Variables 

### Django Configuration
DJANGO_DEBUG=True (False for Production)
DJANGO_SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1, your site domain for production

### Database Configuration (Neon PostgreSQL)
DATABASE_URL=postgresql://user:password@host:port/dbname?sslmode=require&channel_binding=require (get from neon db)

### OpenAI API Configuration
OPENAI_API_KEY=your-openai-api-key-here

### CSRF Configuration (optional, for production deployment)
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com (put your production site)

### OpenAI Model Names
OPENAI_MODEL_NAME=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

## Supported OS

DiscussChat has first-class support for Linux systems. It is designed and tested primarily on Linux, ensuring the best performance and compatibility. While it may work on other operating systems, Linux is recommended for the most reliable experience.
