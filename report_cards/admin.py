from django.contrib import admin

from .models import Admin, Option, Question, Student, StudentProfileChange, Subject


@admin.register(Admin)
class AdminModelAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "user")
    search_fields = ("name", "email", "user__username")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "user")
    search_fields = ("name", "email", "user__username")


@admin.register(StudentProfileChange)
class StudentProfileChangeAdmin(admin.ModelAdmin):
    list_display = ("student", "name", "email", "phone", "status", "created_at")
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


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question_text", "subject")
    list_filter = ("subject",)
    search_fields = ("question_text",)


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("option_text", "question", "is_answer")
    list_filter = ("is_answer",)
    search_fields = ("option_text", "question__question_text")
