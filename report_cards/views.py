import secrets
import smtplib
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import OTPVerificationForm, QuestionCreateForm, StudentProfileChangeForm
from .models import (
    Admin,
    Option,
    Question,
    Student,
    StudentOTP,
    StudentProfileChange,
    Subject,
)

OTP_EXPIRATION = timedelta(minutes=10)
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
PENDING_OTP_USER_SESSION_KEY = "pending_otp_user_id"
PENDING_OTP_BACKEND_SESSION_KEY = "pending_otp_backend"
PENDING_OTP_NEXT_SESSION_KEY = "pending_otp_next"


def _is_admin(user):
    return (
        user.is_staff
        or user.is_superuser
        or Admin.objects.filter(user=user).exists()
    )


def _send_student_otp(student):
    otp = StudentOTP.objects.create(
        student=student,
        code=f"{secrets.randbelow(1_000_000):06d}",
        expires_at=timezone.now() + OTP_EXPIRATION,
    )
    try:
        sent_count = send_mail(
            "Your Quizopedia login OTP",
            (
                f"Your one-time password is {otp.code}. "
                f"It expires in {int(OTP_EXPIRATION.total_seconds() // 60)} minutes."
            ),
            None,
            [student.email],
            fail_silently=False,
        )
    except (OSError, smtplib.SMTPException):
        otp.delete()
        return False

    if sent_count != 1:
        otp.delete()
        return False

    student.otps.exclude(pk=otp.pk).delete()
    return True


def _pending_otp_student(request):
    user_id = request.session.get(PENDING_OTP_USER_SESSION_KEY)
    backend = request.session.get(PENDING_OTP_BACKEND_SESSION_KEY)
    if user_id is None or backend is None:
        return None, None

    student = (
        Student.objects.select_related("user")
        .filter(user_id=user_id)
        .first()
    )
    return student, backend


def _otp_cooldown_seconds(otp, now):
    if otp is None:
        return 0
    remaining = (otp.created_at + OTP_RESEND_COOLDOWN - now).total_seconds()
    return max(0, int(remaining + 0.999))


class RoleBasedLoginView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        user = form.get_user()
        self.request.session.pop(PENDING_OTP_USER_SESSION_KEY, None)
        self.request.session.pop(PENDING_OTP_BACKEND_SESSION_KEY, None)
        self.request.session.pop(PENDING_OTP_NEXT_SESSION_KEY, None)
        student = (
            None
            if _is_admin(user)
            else Student.objects.filter(user=user).first()
        )
        if student:
            now = timezone.now()
            latest_otp = student.otps.order_by("-created_at", "-pk").first()
            if latest_otp is None or _otp_cooldown_seconds(latest_otp, now) == 0:
                if not _send_student_otp(student):
                    form.add_error(
                        None,
                        "We couldn't email your OTP. Please try signing in again later.",
                    )
                    return self.form_invalid(form)

            redirect_url = self.get_redirect_url()
            auth_logout(self.request)
            self.request.session[PENDING_OTP_USER_SESSION_KEY] = user.pk
            self.request.session[PENDING_OTP_BACKEND_SESSION_KEY] = user.backend
            if redirect_url:
                self.request.session[PENDING_OTP_NEXT_SESSION_KEY] = redirect_url
            return redirect("student_otp_verify")

        return super().form_valid(form)

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url

        if _is_admin(self.request.user):
            return reverse("admin_dashboard")
        return reverse("student_dashboard")


def student_otp_verify(request):
    student, backend = _pending_otp_student(request)
    if student is None:
        request.session.pop(PENDING_OTP_USER_SESSION_KEY, None)
        request.session.pop(PENDING_OTP_BACKEND_SESSION_KEY, None)
        request.session.pop(PENDING_OTP_NEXT_SESSION_KEY, None)
        messages.error(request, "Please sign in again to request a verification code.")
        return redirect("login")

    form = OTPVerificationForm(request.POST or None)
    latest_otp = student.otps.order_by("-created_at", "-pk").first()
    now = timezone.now()
    if request.method == "POST" and form.is_valid():
        code_is_valid = (
            latest_otp is not None
            and latest_otp.expires_at > now
            and secrets.compare_digest(latest_otp.code, form.cleaned_data["code"])
        )
        if not code_is_valid:
            form.add_error("code", "That code is incorrect or has expired.")
        elif not student.user.is_active:
            request.session.pop(PENDING_OTP_USER_SESSION_KEY, None)
            request.session.pop(PENDING_OTP_BACKEND_SESSION_KEY, None)
            request.session.pop(PENDING_OTP_NEXT_SESSION_KEY, None)
            messages.error(request, "This account is inactive. Please contact your school.")
            return redirect("login")
        else:
            redirect_url = request.session.pop(PENDING_OTP_NEXT_SESSION_KEY, None)
            request.session.pop(PENDING_OTP_USER_SESSION_KEY, None)
            request.session.pop(PENDING_OTP_BACKEND_SESSION_KEY, None)
            student.otps.all().delete()
            auth_login(request, student.user, backend=backend)
            return redirect(redirect_url or reverse("student_dashboard"))

    return render(
        request,
        "registration/otp_verify.html",
        {
            "form": form,
            "cooldown_seconds": _otp_cooldown_seconds(latest_otp, now),
            "otp_expired": latest_otp is None or latest_otp.expires_at <= now,
        },
    )


@require_POST
def resend_student_otp(request):
    student, _ = _pending_otp_student(request)
    if student is None:
        request.session.pop(PENDING_OTP_USER_SESSION_KEY, None)
        request.session.pop(PENDING_OTP_BACKEND_SESSION_KEY, None)
        request.session.pop(PENDING_OTP_NEXT_SESSION_KEY, None)
        messages.error(request, "Please sign in again to request a verification code.")
        return redirect("login")

    now = timezone.now()
    latest_otp = student.otps.order_by("-created_at", "-pk").first()
    if _otp_cooldown_seconds(latest_otp, now) > 0:
        messages.error(request, "Please wait for the cooldown to finish before requesting another code.")
    elif not _send_student_otp(student):
        messages.error(request, "We couldn't email your OTP. Please try again later.")
    else:
        messages.success(request, "A new verification code has been sent to your email.")
    return redirect("student_otp_verify")


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
        "registered_student_count": Student.objects.filter(
            user__isnull=False
        ).count(),
        "question_count": Question.objects.count(),
        "students": Student.objects.select_related("user").order_by("name")[:6],
        "pending_profile_changes": StudentProfileChange.objects.filter(
            status=StudentProfileChange.Status.PENDING
        ).select_related("student"),
    }
    return render(request, "report_cards/admin_dashboard.html", context)


@login_required
def question_create(request):
    if not _is_admin(request.user):
        raise PermissionDenied

    selected_subject = Subject.objects.filter(
        pk=(
            request.POST.get("subject")
            if request.method == "POST"
            else request.GET.get("subject")
        )
    ).first()
    form = QuestionCreateForm(
        request.POST or None,
        initial={"subject": selected_subject},
    )

    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        with transaction.atomic():
            question.save()
            for label in ("A", "B", "C", "D"):
                Option.objects.create(
                    question=question,
                    option_text=form.cleaned_data[f"option_{label.lower()}"],
                    is_answer=form.cleaned_data["correct_option"] == label,
                )
        messages.success(request, "Question created successfully.")
        return redirect(
            f"{reverse('question_create')}?subject={question.subject_id}"
        )

    questions = (
        selected_subject.questions.prefetch_related("options").order_by("pk")
        if selected_subject
        else Question.objects.none()
    )
    return render(
        request,
        "report_cards/question_create.html",
        {
            "form": form,
            "selected_subject": selected_subject,
            "questions": questions,
            "subjects": Subject.objects.order_by("name"),
        },
    )


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
