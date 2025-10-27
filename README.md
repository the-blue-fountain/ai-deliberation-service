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

### How a Discussion Works

1. **Setup Phase**: A moderator creates a new discussion session by choosing a topic and optionally providing background information or custom instructions for the AI.

2. **Participant Phase**: Multiple people can join the discussion simultaneously. Each participant chats with their own AI assistant, sharing their thoughts and answering follow-up questions. The AI keeps track of what each person says and builds up a profile of their perspective.

3. **Synthesis Phase**: Once participants finish sharing, the AI combines everyone's individual summaries into a comprehensive overview. This highlights common ground, differences of opinion, strong feelings, and areas that need more clarification.

The system is designed to handle multiple discussions at once and keeps all data organized so moderators can review past sessions or run new analyses.

## Creating an account on Neondb

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
5. **Start the application**: Launch the web server.
   ```bash
   python manage.py runserver
   ```

6. **Access the application**: Open your web browser and go to `http://localhost:8000/`. Use participant ID `0` for the moderator dashboard, or `1`, `2`, `3`, etc. for participants.

## Creating an account on Render

## Supported OS

DiscussChat has first-class support for Linux systems. It is designed and tested primarily on Linux, ensuring the best performance and compatibility. While it may work on other operating systems, Linux is recommended for the most reliable experience.
