from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import (
    ContactMessage,
    Option,
    Question,
    Student,
    StudentProfileChange,
    Subject,
)


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


class StudentRegistrationForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = Student
        fields = ("name", "email", "phone")

    def clean_username(self):
        username = self.cleaned_data["username"]
        user_model = get_user_model()
        if user_model._default_manager.filter(
            **{user_model.USERNAME_FIELD: username}
        ).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data["password2"]
        if password1 != password2:
            raise forms.ValidationError("The two password fields did not match.")

        user_model = get_user_model()
        user = user_model(
            **{
                user_model.USERNAME_FIELD: self.cleaned_data.get("username"),
                "email": self.cleaned_data.get("email"),
            }
        )
        try:
            validate_password(password2, user)
        except ValidationError as error:
            self.add_error("password2", error)
        return password2

    def create_user(self):
        user_model = get_user_model()
        return user_model._default_manager.create_user(
            **{
                user_model.USERNAME_FIELD: self.cleaned_data["username"],
                "email": self.cleaned_data["email"],
                "password": self.cleaned_data["password1"],
            }
        )


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("subject", "message")
        widgets = {
            "subject": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 150}
            ),
            "message": forms.Textarea(
                attrs={"class": "form-control", "rows": 5}
            ),
        }

    def clean_subject(self):
        subject = self.cleaned_data["subject"]
        if "\r" in subject or "\n" in subject:
            raise forms.ValidationError("Enter the subject on a single line.")
        return subject


class ContactReplyForm(forms.Form):
    reply = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=10000,
    )


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ("name", "description")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter subject name",
                    "required": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter an optional description",
                    "rows": 4,
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Subject name is required.")

        duplicate = Subject.objects.filter(name__iexact=name)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(
                "A subject with this name already exists."
            )
        return name


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


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ("subject", "question_text", "explanation")


class OptionForm(forms.ModelForm):
    class Meta:
        model = Option
        fields = ("option_text", "is_answer")
        widgets = {
            "is_answer": forms.CheckboxInput(),
        }


class BaseOptionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        active_options = [
            form
            for form in self.forms
            if form.cleaned_data
            and not form.cleaned_data.get("DELETE", False)
            and form.cleaned_data.get("option_text")
        ]
        if len(active_options) < 2:
            raise forms.ValidationError("Add at least two options.")
        if sum(form.cleaned_data.get("is_answer", False) for form in active_options) != 1:
            raise forms.ValidationError("Select exactly one correct option.")


QuestionOptionFormSet = inlineformset_factory(
    Question,
    Option,
    form=OptionForm,
    formset=BaseOptionFormSet,
    extra=4,
    can_delete=True,
)

QuestionUpdateOptionFormSet = inlineformset_factory(
    Question,
    Option,
    form=OptionForm,
    formset=BaseOptionFormSet,
    extra=1,
    can_delete=True,
)
