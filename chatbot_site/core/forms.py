from django import forms

from .models import DiscussionSession


class ParticipantIdForm(forms.Form):
    participant_id = forms.IntegerField(min_value=0, label="Participant ID")


class DiscussionSessionForm(forms.ModelForm):
    # Single objective question shared by all participants.
    objective_question = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control", "placeholder": "Objective question for all participants (leave blank to generate)"}),
        required=False,
        label="Objective question",
    )

    class Meta:
        model = DiscussionSession
        fields = [
            "s_id",
            "topic",
            "objective_question",
            "knowledge_base",
            "user_system_prompt",
            "moderator_system_prompt",
        ]
        widgets = {
            "s_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unique session identifier"}),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "objective_question": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "knowledge_base": forms.Textarea(
                attrs={"rows": 8, "class": "form-control", "placeholder": "Moderator knowledge base for RAG"}
            ),
            "user_system_prompt": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "moderator_system_prompt": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize objective_question from instance
        if self.instance and getattr(self.instance, "objective_question", None):
            self.fields["objective_question"].initial = str(self.instance.objective_question)

    def save(self, commit=True):
        instance = super().save(commit=False)
        # objective_question is managed by the form field
        instance.objective_question = self.cleaned_data.get("objective_question") or ""
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
