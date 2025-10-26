from django import forms

from .models import DiscussionSession


class ParticipantIdForm(forms.Form):
    participant_id = forms.IntegerField(min_value=0, label="Participant ID")


class DiscussionSessionForm(forms.ModelForm):
    # Present objectives as newline-separated textarea for moderator convenience
    objectives_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6, "class": "form-control", "placeholder": "One objective question per line (user 1 on line 1, user 2 on line 2, ...)"}),
        required=False,
        label="Participant objectives (one per line)",
    )

    class Meta:
        model = DiscussionSession
        fields = [
            "s_id",
            "topic",
            "participant_count",
            "knowledge_base",
            "user_system_prompt",
            "moderator_system_prompt",
        ]
        widgets = {
            "s_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unique session identifier"}),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "participant_count": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "knowledge_base": forms.Textarea(
                attrs={"rows": 8, "class": "form-control", "placeholder": "Moderator knowledge base for RAG"}
            ),
            "user_system_prompt": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "moderator_system_prompt": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize objectives_text from instance.objectives
        if self.instance and getattr(self.instance, "objectives", None):
            if isinstance(self.instance.objectives, (list, tuple)):
                self.fields["objectives_text"].initial = "\n".join(
                    str(x) for x in self.instance.objectives
                )

    def clean_participant_count(self):
        value = self.cleaned_data.get("participant_count")
        if value is None:
            return 0
        return int(value)

    def clean_objectives_text(self):
        text = self.cleaned_data.get("objectives_text", "") or ""
        # Convert to list of non-empty lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines

    def save(self, commit=True):
        instance = super().save(commit=False)
        objectives = self.cleaned_data.get("objectives_text")
        if objectives is not None:
            # objectives here is list from clean_objectives_text
            instance.objectives = objectives
        # Ensure participant_count is set
        instance.participant_count = self.cleaned_data.get("participant_count") or 0
        if commit:
            instance.save()
        return instance


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
