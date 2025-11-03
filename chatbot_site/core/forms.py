import json

from django import forms

from .models import DiscussionSession, AIDeliberationSession
from .models import GraderSession, GraderResponse


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
    no_new_information_limit = forms.IntegerField(
        min_value=1,
        initial=2,
        label="Consecutive 'no new info' limit",
        help_text="Number of responses without new information before the assistant advances or closes a question.",
    )

    class Meta:
        model = DiscussionSession
        fields = [
            "s_id",
            "topic",
            "description",
            "question_followup_limit",
            "no_new_information_limit",
            "objective_questions",
            "knowledge_base",
            "user_system_prompt",
            "moderator_system_prompt",
            "user_instructions",
        ]
        widgets = {
            "s_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unique session identifier"}),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={"rows": 6, "class": "form-control", "placeholder": "Detailed description (markdown supported)"}
            ),
            "knowledge_base": forms.Textarea(
                attrs={"rows": 8, "class": "form-control", "placeholder": "Moderator knowledge base for RAG"}
            ),
            "user_system_prompt": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "moderator_system_prompt": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "user_instructions": forms.Textarea(
                attrs={"rows": 4, "class": "form-control", "placeholder": "Optional instructions for participants"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sequence = []
        if self.instance and self.instance.pk:
            sequence = self.instance.get_question_sequence()
            if self.instance.question_followup_limit:
                self.fields["question_followup_limit"].initial = self.instance.question_followup_limit
            if self.instance.no_new_information_limit:
                self.fields["no_new_information_limit"].initial = self.instance.no_new_information_limit
        if not sequence:
            sequence = []
        self.fields["objective_questions"].initial = json.dumps(sequence)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.objective_questions = self.cleaned_data.get("objective_questions", [])
        instance.question_followup_limit = self.cleaned_data.get("question_followup_limit")
        instance.no_new_information_limit = self.cleaned_data.get("no_new_information_limit")
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


class AIDeliberationSessionForm(forms.ModelForm):
    objective_questions = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )
    personas = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )

    class Meta:
        model = AIDeliberationSession
        fields = [
            "s_id",
            "topic",
            "description",
            "objective_questions",
            "personas",
            "user_instructions",
        ]
        widgets = {
            "s_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unique session identifier"}),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={"rows": 6, "class": "form-control", "placeholder": "Detailed session description"}
            ),
            "user_instructions": forms.Textarea(
                attrs={"rows": 4, "class": "form-control", "placeholder": "Optional instructions for AI agents"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        questions = []
        personas = []
        if self.instance and self.instance.pk:
            questions = self.instance.get_question_sequence()
            personas = self.instance.get_personas()
        self.fields["objective_questions"].initial = json.dumps(questions)
        self.fields["personas"].initial = json.dumps(personas)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.objective_questions = self.cleaned_data.get("objective_questions", [])
        instance.personas = self.cleaned_data.get("personas", [])
        if commit:
            instance.save()
        return instance

    def clean_objective_questions(self):
        return self._clean_json_field("objective_questions", "Question list")

    def clean_personas(self):
        return self._clean_json_field("personas", "Personas list")

    def _clean_json_field(self, field_name: str, field_label: str) -> list[str]:
        raw = self.cleaned_data.get(field_name)
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Unable to decode {field_label}.") from exc
        if not isinstance(parsed, list):
            raise forms.ValidationError(f"{field_label} must be an array of strings.")

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


class AISessionSelectionForm(forms.Form):
    session_id = forms.ChoiceField(label="Active AI session", required=False)

    def __init__(self, *args, sessions=None, **kwargs):
        super().__init__(*args, **kwargs)
        session_choices = [("", "Create new AI session")]
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


class GraderSessionForm(forms.ModelForm):
    objective_questions = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = GraderSession
        fields = [
            "s_id",
            "topic",
            "description",
            "objective_questions",
            "knowledge_base",
            "user_instructions",
        ]
        widgets = {
            "s_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unique session identifier"}),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 6, "class": "form-control", "placeholder": "Detailed session description (markdown supported)"}),
            "knowledge_base": forms.Textarea(attrs={"rows": 6, "class": "form-control", "placeholder": "Moderator knowledge base for RAG"}),
            "user_instructions": forms.Textarea(attrs={"rows": 4, "class": "form-control", "placeholder": "Optional instructions for graders"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        questions = []
        if self.instance and self.instance.pk:
            questions = self.instance.get_question_sequence()
        self.fields["objective_questions"].initial = json.dumps(questions)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.objective_questions = self.cleaned_data.get("objective_questions", [])
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


class GraderSessionSelectionForm(forms.Form):
    session_id = forms.ChoiceField(label="Active grader session", required=False)

    def __init__(self, *args, sessions=None, **kwargs):
        super().__init__(*args, **kwargs)
        session_choices = [("", "Create new grader session")]
        if sessions is not None:
            session_choices.extend(
                (str(session.pk), f"{session.s_id} — {session.topic or 'No topic'}")
                for session in sessions
            )
        self.fields["session_id"].choices = session_choices
        self.fields["session_id"].widget.attrs.update({"class": "form-select"})


class GraderResponseForm(forms.Form):
    """Form presented to graders where each objective question gets a score and a reason."""

    # This form will be created dynamically by the view based on the session questions.
    additional_comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        label="Any additional comments",
    )
