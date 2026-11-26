from django.contrib import admin

from .forms import BaseOptionFormSet, StudentRegistrationForm
from .models import (
    Admin,
    ContactMessage,
    Option,
    Question,
    Student,
    StudentProfileChange,
    Subject,
)


@admin.register(Admin)
class AdminModelAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "user")
    search_fields = ("name", "email", "user__username")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "user")
    search_fields = ("name", "email", "user__username")

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = StudentRegistrationForm if obj is None else self.form
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, _request, obj=None):
        if obj is None:
            return (
                (None, {"fields": ("name", "email", "phone")}),
                (
                    "Student login",
                    {"fields": ("username", "password1", "password2")},
                ),
            )
        return ((None, {"fields": ("name", "email", "phone", "user")}),)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = form.create_user()
        super().save_model(request, obj, form, change)


@admin.register(StudentProfileChange)
class StudentProfileChangeAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "name",
        "email",
        "phone",
        "status",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("student__name", "name", "email")
    readonly_fields = (
        "student",
        "name",
        "email",
        "phone",
        "status",
        "created_at",
        "reviewed_at",
    )
    fields = ("student", "name", "email", "phone", "status", "created_at", "reviewed_at")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender_name", "sender_email", "created_at", "replied_at")
    search_fields = ("subject", "sender_name", "sender_email", "message")
    readonly_fields = (
        "user",
        "sender_name",
        "sender_email",
        "subject",
        "message",
        "created_at",
        "reply",
        "replied_at",
    )


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


class QuestionOptionInline(admin.TabularInline):
    model = Option
    formset = BaseOptionFormSet
    extra = 4
    can_delete = True


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question_text", "subject")
    list_filter = ("subject",)
    search_fields = ("question_text",)
    inlines = (QuestionOptionInline,)


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("option_text", "question", "is_answer")
    list_filter = ("is_answer",)
    search_fields = ("option_text", "question__question_text")
