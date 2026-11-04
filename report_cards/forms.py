from django import forms

from .models import Question, StudentProfileChange


class StudentProfileChangeForm(forms.ModelForm):
    class Meta:
        model = StudentProfileChange
        fields = ("name", "email", "phone")


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
