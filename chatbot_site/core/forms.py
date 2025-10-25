from django import forms

from .models import DiscussionSession


class ParticipantIdForm(forms.Form):
    participant_id = forms.IntegerField(min_value=0, label="Participant ID")


class DiscussionSessionForm(forms.ModelForm):
    class Meta:
        model = DiscussionSession
        fields = [
            "s_id",
            "topic",
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
