# Prompts Guide - DiscussChat

This guide explains each prompt used in DiscussChat, its purpose, and how to customize it.

## Overview

All prompts are centralized in `prompts/prompts.py` and are organized by bot role:
- **User Bot Prompts**: Guide the AI in facilitating individual user conversations
- **Moderator Bot Prompts**: Guide the AI in synthesizing multiple perspectives

## User Bot Prompts

### 1. USER_BOT_BASE_PROMPT
**Role**: Establishes the core personality and behavior of the user-facing chatbot.

**Usage**: Foundation for all user interactions. Defines:
- Reporter/investigator persona
- Topic focus and boundary management
- Respectful challenge and clarification seeking
- Emotional attentiveness

**Customization**: Modify this to change the bot's personality (e.g., "You are a critical analyst..." or "You are a supportive listener...")

**Example Extension**:
```python
# Make the bot more Socratic
USER_BOT_BASE_PROMPT = (
    "You are a skilled Socratic facilitator using questioning to help users "
    "explore their own thinking. Ask probing questions rather than providing "
    "assertions. Guide users to discover inconsistencies themselves..."
)
```

---

### 2. USER_BOT_REASONING_PROMPT
**Role**: Instructs the bot to perform structured internal analysis before responding.

**Usage**: Ensures the bot:
- Breaks down user responses into clear points
- Compares new input against prior knowledge
- Detects genuinely new information vs. repetition
- Identifies vagueness requiring clarification

**Customization**: Modify the reasoning strategy (e.g., add "consider cultural context" or "track sentiment changes")

**Example Extension**:
```python
USER_BOT_REASONING_PROMPT = (
    "Work through the response with explicit reasoning. Consider:"
    "\n- Cultural or contextual factors"
    "\n- Emotional undertones in language"
    "\n- Contradictions with prior statements"
    "\n- Areas of certainty vs. uncertainty..."
)
```

---

### 3. USER_BOT_OUTPUT_INSTRUCTIONS
**Role**: Specifies the exact JSON structure the bot must return during each turn.

**Usage**: Enforces parsing reliability. Bot must always return:
- `assistant_reply`: What to say to the user
- `breakdown`: Key points from their response
- `clarification_requests`: Questions for the user
- `new_information`: Boolean flag for information tracking
- `temp_md_entry`: Accumulating notes (no duplication)
- `reasoning_notes`: Justification for the new_information flag

**Customization**: Add new fields if needed (careful - backend parsing must be updated too)

**⚠️ Do Not Modify Lightly**: Changing this requires updating `UserConversationService.process_user_message()` to parse new fields.

---

### 4. USER_BOT_FINAL_PROMPT
**Role**: Instructs the bot to synthesize all live notes into a comprehensive final analysis.

**Usage**: Called when conversation ends (manual stop or 15-message limit). Takes accumulated `scratchpad` and generates `views_markdown` (final analysis).

**What It Produces**:
- Polished markdown document
- User's positions with nuance
- Strength of sentiment indicators
- Areas of uncertainty and contradictions
- Professional presentation suitable for moderator review

**Customization**: Modify to emphasize different aspects (e.g., "prioritize novel insights over consensus")

**Example Extension**:
```python
USER_BOT_FINAL_PROMPT = (
    "You have completed the conversation. Synthesize temp.md into a final analysis "
    "emphasizing novel insights and areas of uncertainty. Be critical: highlight "
    "weak reasoning or unsupported claims. Structure as markdown with headings..."
)
```

---

### 5. DEFAULT_USER_SYSTEM_PROMPT
**Role**: Default system prompt combining base, reasoning, and professional guidelines.

**Usage**: Used by `UserConversationService` if the moderator hasn't customized the prompt.

**Structure**: 
```
BASE_PROMPT (personality)
+ REASONING_PROMPT (analysis strategy)
+ Professional guidelines (tone, transparency)
```

**Customization**: Moderators can override this per-session via the "Moderator Controls" form. Custom prompts are stored in the session and used instead of the default.

---

## Moderator Bot Prompts

### 6. MODERATOR_ANALYSIS_PROMPT
**Role**: Instructs the moderator bot to analyze and synthesize multiple user perspectives.

**Usage**: Called after all user conversations complete. Takes all user `views_markdown` documents and produces:
- `moderator_temp`: Internal reasoning and synthesis process
- `summary_md`: Structured JSON analysis

**What It Produces** (in `summary_md`):
```json
{
  "consensus": ["areas of agreement..."],
  "disagreement": ["points of divergence..."],
  "strength_of_sentiment": ["emotional intensity..."],
  "confusion": ["unclear areas..."],
  "missing_information": ["gaps in coverage..."]
}
```

**Customization**: Modify analysis dimensions (e.g., add "innovation potential" or "implementation feasibility")

**Example Extension**:
```python
MODERATOR_ANALYSIS_PROMPT = (
    "Analyze user perspectives and also identify:"
    "\n- Power dynamics or status concerns"
    "\n- Feasibility of proposed solutions"
    "\n- Hidden assumptions..."
)
```

---

### 7. DEFAULT_MODERATOR_SYSTEM_PROMPT
**Role**: Default system prompt for moderator synthesis when not customized.

**Usage**: Used by `ModeratorAnalysisService` if the session lacks custom prompt.

**Structure**: Combines analysis strategy, JSON formatting, and output field definitions.

**Customization**: Moderators can override via session form. Custom prompts applied to synthesis analysis.

---

## Prompt Customization Guide

### When to Customize

1. **User Bot Prompts**: 
   - Different discussion style (Socratic vs. investigative vs. empathetic)
   - Specific expertise required (legal, medical, technical)
   - Domain-specific terminology or context

2. **Moderator Bot Prompts**:
   - Different analysis dimensions needed
   - Specific synthesis approach
   - Custom output structure required

### How to Customize Per-Session

1. **Create Session** in Moderator Dashboard
2. **Scroll to "Moderator Controls"**
3. **Modify fields**:
   - "User System Prompt" - custom instructions for user bot
   - "Moderator System Prompt" - custom instructions for moderator synthesis
4. **Click "Save Changes"** or **"Save As New"** (for new session)

### How to Customize Global Defaults

Edit `prompts/prompts.py`:
```python
DEFAULT_USER_SYSTEM_PROMPT = (
    f"{YOUR_CUSTOM_BASE_PROMPT}\n\n"
    f"{YOUR_CUSTOM_REASONING_PROMPT}\n\n"
    "Keep professional and inquisitive."
)
```

Then update Django defaults:
```python
# core/models.py
default=prompts.DEFAULT_USER_SYSTEM_PROMPT,
```

**Note**: Changing global defaults affects only new sessions. Existing sessions keep their original prompts.

---

## Example: Custom Domain-Specific Session

### Healthcare Discussion

```
Session ID: healthcare-2025
Topic: Doctor-Patient Communication

User System Prompt:
"You are an experienced healthcare consultant facilitating discussion 
about doctor-patient communication. Participants are medical professionals 
with 5+ years experience. Focus on: barriers to communication, 
cultural competence, time pressures, patient autonomy. Challenge 
assumptions respectfully using evidence-based examples."

Moderator System Prompt:
"Synthesize perspectives from medical professionals on doctor-patient 
communication. Organize findings by: institutional barriers, behavioral 
factors, technical/systemic issues, and recommendations. Highlight 
areas where practitioners agree on root causes despite different solutions."
```

### Legal Discussion

```
Session ID: regulatory-compliance
Topic: Emerging Privacy Regulations

User System Prompt:
"You are an expert regulatory affairs consultant. Explore how 
organizations interpret and prepare for emerging privacy regulations. 
Participants include compliance officers, legal counsel, and technologists. 
Focus on ambiguities, implementation costs, competitive advantage, and 
risk mitigation strategies."
```

---

## Prompt Best Practices

### ✅ Do

- **Be Specific**: "Investigate barriers to adoption" vs. "Talk about barriers"
- **Set Context**: Mention if participants are experts, general public, etc.
- **Define Output**: Specify structure, length, tone expectations
- **Test**: Create a test session, run RAG, start conversations to verify prompt behavior
- **Document**: Add comments in prompts.py explaining custom prompts for your team

### ❌ Don't

- **Override USER_BOT_OUTPUT_INSTRUCTIONS lightly**: Output format is parsed by backend
- **Make prompts too long**: Token usage increases; keep under 500 words for system prompts
- **Use conflicting instructions**: "Be brief" + "Provide detailed analysis" creates confusion
- **Assume context**: If new team member uses your session, they should understand the prompt's intent
- **Ignore token limits**: Very complex prompts + long history can hit token limits

---

## Debugging Prompts

### Issue: Bot keeps repeating user points

**Likely Cause**: USER_BOT_REASONING_PROMPT not effectively comparing against prior points

**Fix**:
```python
USER_BOT_REASONING_PROMPT = (
    "Compare EACH point in the new response against the entire prior history. "
    "If you see even a slight rewording of something said before, flag it as "
    "not new. Only mark as new_information if the substance is genuinely novel..."
)
```

### Issue: Moderator summary lacks specific insights

**Likely Cause**: MODERATOR_ANALYSIS_PROMPT too generic

**Fix**: Add specific dimensions:
```python
MODERATOR_ANALYSIS_PROMPT = (
    "...Also identify: (1) behavioral patterns common across users, "
    "(2) contradictions that reveal hidden assumptions, (3) solutions "
    "that address multiple concerns..."
)
```

### Issue: Bot not respecting topic boundaries

**Likely Cause**: USER_BOT_BASE_PROMPT doesn't emphasize topic focus

**Fix**:
```python
USER_BOT_BASE_PROMPT = (
    "You are discussing ONLY: [specific topic]. "
    "Immediately redirect if participants drift to related but out-of-scope topics. "
    "Say 'That's interesting, but outside today's scope: [topic]...'"
)
```

---

## Monitoring Prompt Quality

Check these metrics:

1. **new_information flag distribution**: ~50-60% should be True for active discussions
2. **Clarification requests frequency**: 1-2 per user message suggests good probing
3. **Moderator summary structure**: All 5 categories populated indicates comprehensive analysis
4. **User analysis length**: 300-500 words suggests substantive synthesis

---

## Prompt Engineering Resources

- OpenAI Prompt Engineering Guide: https://platform.openai.com/docs/guides/prompt-engineering
- Chain-of-Thought Prompting: Wei et al., https://arxiv.org/abs/2201.11903
- Prompt Injection Risks: https://owasp.org/www-project-top-10-for-large-language-model-applications/

---

**Last Updated**: October 2025
