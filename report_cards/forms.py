from django import forms
from django.core.validators import RegexValidator

from .models import Question, StudentProfileChange, Subject


class OTPVerificationForm(forms.Form):
    code = forms.CharField(
        label="One-time password",
        max_length=6,
        min_length=6,
        validators=[
            RegexValidator(
                regex=r"^\d{6}$",
                message="Enter the six-digit code from your email.",
            )
        ],
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
            }
        ),
    )


class StudentProfileChangeForm(forms.ModelForm):
    class Meta:
        model = StudentProfileChange
        fields = ("name", "email", "phone")


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ("name", "description")


class QuestionCreateForm(forms.ModelForm):
    option_a = forms.CharField(max_length=255, label="Option A")
    option_b = forms.CharField(max_length=255, label="Option B")
    option_c = forms.CharField(max_length=255, label="Option C")
    option_d = forms.CharField(max_length=255, label="Option D")
    correct_option = forms.ChoiceField(
        choices=(
            ("A", "Option A"),
            ("B", "Option B"),
            ("C", "Option C"),
            ("D", "Option D"),
        ),
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Question
        fields = ("subject", "question_text", "explanation")
