from django.contrib import admin

from .models import Admin, Student


@admin.register(Admin)
class AdminModelAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "user")
    search_fields = ("name", "email", "user__username")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "user")
    search_fields = ("name", "email", "user__username")
