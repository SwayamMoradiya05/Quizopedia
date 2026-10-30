from django import forms

from .models import StudentProfileChange


class StudentProfileChangeForm(forms.ModelForm):
    class Meta:
        model = StudentProfileChange
        fields = ("name", "email", "phone")

