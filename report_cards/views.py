from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import StudentProfileChangeForm
from .models import Admin, Student, StudentProfileChange


def _is_admin(user):
    return (
        user.is_staff
        or user.is_superuser
        or Admin.objects.filter(user=user).exists()
    )


class RoleBasedLoginView(LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url

        if _is_admin(self.request.user):
            return reverse("admin_dashboard")
        return reverse("student_dashboard")


def home(request):
    if request.user.is_authenticated:
        if _is_admin(request.user):
            return redirect("admin_dashboard")
        return redirect("student_dashboard")
    return redirect("login")


@login_required
def admin_dashboard(request):
    if not _is_admin(request.user):
        raise PermissionDenied

    context = {
        "student_count": Student.objects.count(),
        "admin_count": Admin.objects.count(),
        "linked_student_count": Student.objects.filter(user__isnull=False).count(),
        "students": Student.objects.select_related("user").order_by("name")[:6],
        "pending_profile_changes": StudentProfileChange.objects.filter(
            status=StudentProfileChange.Status.PENDING
        ).select_related("student"),
    }
    return render(request, "report_cards/admin_dashboard.html", context)


@login_required
def student_dashboard(request):
    student = Student.objects.filter(user=request.user).first()
    return render(
        request,
        "report_cards/student_dashboard.html",
        {
            "student": student,
            "display_name": (
                student.name
                if student
                else request.user.get_full_name() or request.user.get_username()
            ),
        },
    )


@login_required
def profile(request):
    if _is_admin(request.user):
        admin_profile = Admin.objects.filter(user=request.user).first()
        return render(
            request,
            "report_cards/profile.html",
            {
                "is_admin_profile": True,
                "profile_name": (
                    admin_profile.name
                    if admin_profile
                    else request.user.get_full_name() or request.user.get_username()
                ),
                "profile_email": (
                    admin_profile.email if admin_profile else request.user.email
                ),
                "profile_phone": admin_profile.phone if admin_profile else "",
            },
        )

    student = Student.objects.filter(user=request.user).first()
    pending_change = (
        student.profile_changes.filter(
            status=StudentProfileChange.Status.PENDING
        ).first()
        if student
        else None
    )
    return render(
        request,
        "report_cards/profile.html",
        {
            "is_admin_profile": False,
            "student": student,
            "pending_change": pending_change,
            "profile_name": (
                student.name
                if student
                else request.user.get_full_name() or request.user.get_username()
            ),
            "profile_email": student.email if student else request.user.email,
            "profile_phone": student.phone if student else "",
        },
    )


@login_required
def student_profile_edit(request):
    if _is_admin(request.user):
        raise PermissionDenied

    student = Student.objects.filter(user=request.user).first()
    if student is None:
        raise PermissionDenied

    pending_change = student.profile_changes.filter(
        status=StudentProfileChange.Status.PENDING
    ).first()
    form = StudentProfileChangeForm(
        request.POST or None,
        instance=pending_change,
        initial=(
            None
            if pending_change
            else {
                "name": student.name,
                "email": student.email,
                "phone": student.phone,
            }
        ),
    )
    if request.method == "POST" and form.is_valid():
        change = form.save(commit=False)
        change.student = student
        change.status = StudentProfileChange.Status.PENDING
        change.save()
        messages.success(request, "Your profile update was submitted for admin approval.")
        return redirect("profile")

    return render(
        request,
        "report_cards/student_profile_edit.html",
        {"form": form, "student": student, "pending_change": pending_change},
    )


@login_required
@require_POST
def review_student_profile_change(request, change_id, decision):
    if not _is_admin(request.user):
        raise PermissionDenied
    if decision not in (
        StudentProfileChange.Status.APPROVED,
        StudentProfileChange.Status.REJECTED,
    ):
        raise PermissionDenied

    change = get_object_or_404(
        StudentProfileChange.objects.select_related("student"),
        pk=change_id,
        status=StudentProfileChange.Status.PENDING,
    )
    with transaction.atomic():
        if decision == StudentProfileChange.Status.APPROVED:
            change.student.name = change.name
            change.student.email = change.email
            change.student.phone = change.phone
            change.student.save(update_fields=("name", "email", "phone"))
        change.status = decision
        change.reviewed_at = timezone.now()
        change.save(update_fields=("status", "reviewed_at"))
    messages.success(
        request,
        f"Student profile change {change.get_status_display().lower()}.",
    )
    return redirect("admin_dashboard")
