from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import Admin, Student


class RoleBasedLoginView(LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url

        if (
            self.request.user.is_staff
            or self.request.user.is_superuser
            or Admin.objects.filter(user=self.request.user).exists()
        ):
            return reverse("admin_dashboard")
        return reverse("student_dashboard")


def home(request):
    if request.user.is_authenticated:
        if (
            request.user.is_staff
            or request.user.is_superuser
            or Admin.objects.filter(user=request.user).exists()
        ):
            return redirect("admin_dashboard")
        return redirect("student_dashboard")
    return redirect("login")


@login_required
def admin_dashboard(request):
    if not (request.user.is_staff or request.user.is_superuser):
        if not Admin.objects.filter(user=request.user).exists():
            raise PermissionDenied

    context = {
        "student_count": Student.objects.count(),
        "admin_count": Admin.objects.count(),
        "linked_student_count": Student.objects.filter(user__isnull=False).count(),
        "students": Student.objects.select_related("user").order_by("name")[:6],
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
