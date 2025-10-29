import json

from django import forms

from .models import DiscussionSession


class ParticipantIdForm(forms.Form):
    participant_id = forms.IntegerField(min_value=0, label="Participant ID")


class DiscussionSessionForm(forms.ModelForm):
    objective_questions = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )
    question_followup_limit = forms.IntegerField(
        min_value=1,
        initial=3,
        label="Follow-up limit per question",
        help_text="Maximum number of participant replies to explore before moving to the next question.",
    )

    class Meta:
        model = DiscussionSession
        fields = [
            "s_id",
            "topic",
            "question_followup_limit",
            "objective_questions",
            "knowledge_base",
            "user_system_prompt",
            "moderator_system_prompt",
        ]
        widgets = {
            "s_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unique session identifier"}),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "knowledge_base": forms.Textarea(
                attrs={"rows": 8, "class": "form-control", "placeholder": "Moderator knowledge base for RAG"}
            ),
            "user_system_prompt": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "moderator_system_prompt": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sequence = []
        if self.instance and self.instance.pk:
            sequence = self.instance.get_question_sequence()
            if self.instance.question_followup_limit:
                self.fields["question_followup_limit"].initial = self.instance.question_followup_limit
        if not sequence:
            sequence = []
        self.fields["objective_questions"].initial = json.dumps(sequence)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.objective_questions = self.cleaned_data.get("objective_questions", [])
        instance.question_followup_limit = self.cleaned_data.get("question_followup_limit")
        if commit:
            instance.save()
        return instance

    def clean_objective_questions(self):
        raw = self.cleaned_data.get("objective_questions")
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Unable to decode question list.") from exc
        if not isinstance(parsed, list):
            raise forms.ValidationError("Question list must be an array of strings.")

        cleaned: list[str] = []
        for entry in parsed:
            text = str(entry).strip()
            if text:
                cleaned.append(text)
        return cleaned


class SessionSelectionForm(forms.Form):
    session_id = forms.ChoiceField(label="Active session", required=False)

    def __init__(self, *args, sessions=None, **kwargs):
        super().__init__(*args, **kwargs)
        session_choices = [("", "Create new session")]
        if sessions is not None:
            session_choices.extend(
                (str(session.pk), f"{session.s_id} — {session.topic or 'No topic'}")
                for session in sessions
            )
        self.fields["session_id"].choices = session_choices
        self.fields["session_id"].widget.attrs.update({"class": "form-select"})


class UserMessageForm(forms.Form):
    message = forms.CharField(
        label="Your Response",
        widget=forms.Textarea(attrs={"rows": 5, "class": "form-control"}),
        max_length=4000,
    )
