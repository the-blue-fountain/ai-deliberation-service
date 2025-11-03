# Grader Feature - Quick Start Guide

## What Was Added

A complete **Grader** mode for the AI Deliberation Service that allows moderators to run structured evaluation/feedback sessions where participants assign numeric scores (1–10) to specific features and provide written justification.

## How to Use

### For Moderators

1. **Access the Grader**
   - Open the application and go to the deliberation system choice page
   - Click the **"Grader"** button (new third option alongside "AI-Human" and "AI-AI")

2. **Create a Grading Session**
   - Click **"New Session"** in the modal that appears
   - Fill in:
     - **Session ID**: Unique identifier (e.g., "product-feedback-2024")
     - **Topic**: Title (e.g., "Mobile App v2.0 Evaluation")
     - Click **"Create"**

3. **Configure the Session**
   - **Description**: Add markdown-formatted context (supports up to 6000+ words)
     ```markdown
     # Evaluation Criteria
     Please rate each feature on a scale of 1-10...
     ```
   - **Objective Questions**: Add evaluation criteria
     - Type a question in the text box
     - Click **"Add"**
     - Use **Up/Down** buttons to reorder questions
     - Use **Remove** button to delete a question
   - **Knowledge Base** (optional): Paste reference materials
   - **User Instructions** (optional): Add guidance for graders

4. **Activate the Session**
   - Click **"Activate Session"** to make it active
   - Active session is what participants will access

5. **Collect Responses**
   - Share the grader URL with participants:
     ```
     http://your-domain/grader/user/<user_id>/
     ```
   - Example: `/grader/user/101/`, `/grader/user/102/`, etc.

6. **Analyze Results**
   - Once responses are collected, click **"Analyze Responses"**
   - System calculates:
     - Average score for each feature
     - AI-generated summaries of participant feedback per feature
   - Results are saved and displayed as markdown

7. **Download Data**
   - Click **"Download Responses (CSV)"** to get a spreadsheet with:
     - User ID for each participant
     - Each participant's scores and reasons for each question
     - Additional comments from each participant

### For Participants

1. **Access the Grading Form**
   - Navigate to provided URL: `/grader/user/<your_id>/`
   - Example: `/grader/user/101/`

2. **Review the Context**
   - Read the session description (formatted as markdown)
   - Understand what you're evaluating

3. **Assign Scores and Reasons**
   - For **each objective question**:
     - Enter a **score from 1 to 10** (where 1 = worst, 10 = best)
     - Write a **reason** for your score (e.g., "This feature is intuitive because...")
   - You can add **optional additional comments** at the bottom

4. **Submit**
   - Click **"Submit Scores"**
   - Get confirmation that your feedback was saved

## Key Features

### For Moderators
✅ Large description support (up to 6000+ words, markdown-formatted)  
✅ Dynamic question builder with reordering  
✅ Optional knowledge base for RAG (Retrieval-Augmented Generation)  
✅ AI-powered analysis (calculates averages, summarizes feedback)  
✅ CSV export (all participant scores and reasons)  
✅ Session activation control  

### For Participants
✅ Clean, simple 1–10 scoring interface  
✅ Required reason field (prevents thoughtless scores)  
✅ Optional additional comments  
✅ Markdown-formatted session descriptions  
✅ Session-based isolation (separate response per session)  

## Database & Structure

- **GraderSession** table: Stores session configuration, questions, and metadata
- **GraderResponse** table: Stores each participant's submission (scores, reasons, comments)
- One response per participant per session (enforced via unique constraint)
- All data persists in PostgreSQL database

## Example Workflow

### Scenario: Evaluating a Product Redesign

1. **Moderator creates session:**
   - Topic: "Mobile App v2.0 Redesign Evaluation"
   - Questions:
     - "How intuitive is the new navigation?"
     - "How visually appealing is the design?"
     - "How responsive does the app feel?"
   - Description: Includes background on the redesign

2. **Moderator activates and shares:**
   - URL shared: `/grader/user/101/`, `/grader/user/102/`, `/grader/user/103/`

3. **Participants submit:**
   - User 101: Gives 8/10 for navigation ("Clear icons, good labels")
   - User 102: Gives 7/10 for navigation ("Could improve back button placement")
   - User 103: Gives 9/10 for navigation ("Best redesign yet!")

4. **Moderator analyzes:**
   - Clicks "Analyze Responses"
   - Sees average score: 8.0/10 for navigation
   - AI summarizes: "Participants praised clear iconography and labeling, with one suggestion to improve back button placement"

5. **Moderator exports:**
   - Downloads CSV with all data for reporting/analysis

## Database Tables (Reference)

### core_gradersession
```
id (PK)
s_id (unique)
topic
description
objective_questions (JSON)
knowledge_base
rag_chunk_count
rag_last_built_at
user_instructions
is_active
created_at
updated_at
```

### core_graderresponse
```
id (PK)
session_id (FK)
user_id
scores (JSON)
reasons (JSON)
additional_comments
submitted_at
unique(session_id, user_id)
```

## Troubleshooting

**Q: How do participants know which URL to visit?**  
A: Share the URL manually or integrate into your invite system. Example: "Please visit `/grader/user/101/` to provide feedback."

**Q: What if a participant submits multiple times?**  
A: Their response is updated (not duplicated) due to the unique constraint on (session_id, user_id).

**Q: Can I modify questions after participants have started?**  
A: Yes, but existing responses will still align with the original question count. Modify carefully.

**Q: How are the AI summaries generated?**  
A: OpenAI (GPT model) is called for each question, concatenating all participant reasons and requesting a 3–6 sentence summary. Falls back gracefully if API fails.

**Q: Can I see individual participant responses before analyzing?**  
A: Yes, via Django admin: `/admin/core/graderresponse/` to inspect raw data.

## Architecture Summary

```
System Choice Page
    ↓
    ├─→ Grader Entry Point
         ↓
         ├─→ Grader Moderator Dashboard (Setup & Analysis)
         │    ├─ Create/Edit Session
         │    ├─ Manage Questions
         │    ├─ Activate & RAG
         │    ├─ Analyze (avg + LLM summary)
         │    └─ Export CSV
         │
         └─→ Grader User View (Participant Submission)
              ├─ View Session & Questions
              ├─ Enter Scores & Reasons
              └─ Submit Responses
```

## Files & Locations

- **Models**: `chatbot_site/core/models.py` (GraderSession, GraderResponse)
- **Views**: `chatbot_site/core/views.py` (5 grader functions)
- **Forms**: `chatbot_site/core/forms.py` (3 grader forms)
- **URLs**: `chatbot_site/core/urls.py` (4 grader routes)
- **Templates**: `chatbot_site/templates/core/grader_*.html` (3 templates)
- **Admin**: `chatbot_site/core/admin.py` (GraderSessionAdmin, GraderResponseAdmin)
- **Migration**: `chatbot_site/core/migrations/0013_add_grader_models.py`

## Next Steps

1. **Test the feature** in your local/staging environment
2. **Create a grader session** with test questions
3. **Invite testers** to submit scores at `/grader/user/<id>/`
4. **Analyze results** and verify CSV export
5. **Deploy** to production when ready

---

**Need Help?**
- See `GRADER_FEATURE.md` for detailed technical documentation
- Check `IMPLEMENTATION_SUMMARY.md` for a complete list of changes
- Review `PROMPTS_GUIDE.md` for any LLM customization
