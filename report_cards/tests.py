from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Admin,
    Option,
    Question,
    Student,
    StudentOTP,
    StudentProfileChange,
    Subject,
)


class SampleDataTests(TestCase):
    def test_sample_data_is_available_and_models_are_registered(self):
        self.assertGreaterEqual(Student.objects.count(), 5)
        self.assertGreaterEqual(Subject.objects.count(), 3)
        self.assertGreaterEqual(Question.objects.count(), 10)
        self.assertTrue(
            all(
                Question.objects.filter(subject=subject).exists()
                for subject in Subject.objects.all()
            )
        )
        self.assertTrue(
            all(
                admin.site.is_registered(model)
                for model in (
                    Admin,
                    Student,
                    StudentProfileChange,
                    Subject,
                    Question,
                    Option,
                )
            )
        )
        self.assertTrue(
            all(question.options.count() == 4 for question in Question.objects.all())
        )
        self.assertTrue(
            all(
                question.options.filter(is_answer=True).count() == 1
                for question in Question.objects.all()
            )
        )


class AuthenticationTests(TestCase):
    def create_user(self, username, *, is_staff=False):
        return get_user_model().objects.create_user(
            username=username,
            password="secure-test-password",
            is_staff=is_staff,
        )

    def test_login_redirects_admin_to_admin_dashboard(self):
        user = self.create_user("testadmin", is_staff=True)

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "secure-test-password"},
        )

        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 200)

    def test_login_redirects_student_to_student_dashboard(self):
        user = self.create_user("teststudent")
        Student.objects.create(
            user=user,
            name="Test Student",
            email="student@example.com",
            phone="555-0100",
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "secure-test-password"},
        )

        self.assertRedirects(response, reverse("student_otp_verify"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        otp = StudentOTP.objects.get(student__user=user)
        response = self.client.post(
            reverse("student_otp_verify"),
            {"code": otp.code},
        )
        self.assertRedirects(response, reverse("student_dashboard"))
        dashboard = self.client.get(reverse("student_dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Test Student")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_student_login_creates_and_emails_expiring_otp(self):
        user = self.create_user("otpstudent")
        student = Student.objects.create(
            user=user,
            name="OTP Student",
            email="otpstudent@example.com",
            phone="555-0102",
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "secure-test-password"},
        )

        self.assertRedirects(response, reverse("student_otp_verify"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        otp = StudentOTP.objects.get(student=student)
        self.assertRegex(otp.code, r"^\d{6}$")
        self.assertGreater(otp.expires_at, timezone.now())
        self.assertLessEqual(
            otp.expires_at,
            timezone.now() + timedelta(minutes=10),
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [student.email])
        self.assertIn(otp.code, mail.outbox[0].body)

        response = self.client.post(
            reverse("student_otp_verify"),
            {"code": otp.code},
        )
        self.assertRedirects(response, reverse("student_dashboard"))
        self.assertFalse(StudentOTP.objects.filter(student=student).exists())
        self.assertEqual(
            self.client.get(reverse("student_dashboard")).status_code,
            200,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_expired_student_otp_does_not_log_in(self):
        user = self.create_user("expiredotpstudent")
        student = Student.objects.create(
            user=user,
            name="Expired OTP Student",
            email="expired@example.com",
            phone="555-0103",
        )
        self.client.post(
            reverse("login"),
            {"username": user.username, "password": "secure-test-password"},
        )
        otp = StudentOTP.objects.get(student=student)

        with patch("report_cards.views.timezone.now", return_value=otp.expires_at):
            response = self.client.post(
                reverse("student_otp_verify"),
                {"code": otp.code},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That code is incorrect or has expired.")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertRedirects(
            self.client.get(reverse("student_dashboard")),
            f"{reverse('login')}?next={reverse('student_dashboard')}",
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_resend_otp_enforces_cooldown_and_sends_a_new_code_afterward(self):
        user = self.create_user("resendotpstudent")
        student = Student.objects.create(
            user=user,
            name="Resend OTP Student",
            email="resend@example.com",
            phone="555-0104",
        )
        self.client.post(
            reverse("login"),
            {"username": user.username, "password": "secure-test-password"},
        )
        original_otp = StudentOTP.objects.get(student=student)

        response = self.client.get(reverse("student_otp_verify"))
        self.assertContains(response, "disabled")
        self.assertContains(response, "You can request another code in")
        response = self.client.post(reverse("resend_student_otp"))
        self.assertRedirects(
            response,
            reverse("student_otp_verify"),
            fetch_redirect_response=False,
        )
        self.assertEqual(StudentOTP.objects.filter(student=student).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(
            self.client.get(reverse("student_otp_verify")),
            "Please wait for the cooldown to finish",
        )

        StudentOTP.objects.filter(pk=original_otp.pk).update(
            created_at=timezone.now() - timedelta(seconds=61),
        )
        response = self.client.post(reverse("resend_student_otp"))
        self.assertRedirects(
            response,
            reverse("student_otp_verify"),
            fetch_redirect_response=False,
        )
        self.assertEqual(StudentOTP.objects.filter(student=student).count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertContains(
            self.client.get(reverse("student_otp_verify")),
            "A new verification code has been sent",
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_invalid_student_login_does_not_create_or_email_otp(self):
        user = self.create_user("invalidotpstudent")
        Student.objects.create(
            user=user,
            name="OTP Student",
            email="otpstudent@example.com",
            phone="555-0102",
        )

        self.client.post(
            reverse("login"),
            {"username": user.username, "password": "wrong-password"},
        )

        self.assertFalse(StudentOTP.objects.exists())
        self.assertEqual(mail.outbox, [])

    @patch("report_cards.views.send_mail", return_value=0)
    def test_student_login_is_rejected_when_otp_email_cannot_be_sent(self, send_mail):
        user = self.create_user("undeliverableotp")
        student = Student.objects.create(
            user=user,
            name="OTP Student",
            email="otpstudent@example.com",
            phone="555-0102",
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "secure-test-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "We couldn't email your OTP. Please try signing in again later.",
            response.context["form"].non_field_errors(),
        )
        self.assertFalse(StudentOTP.objects.filter(student=student).exists())
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        send_mail.assert_called_once()

    def test_linked_admin_profile_receives_admin_dashboard(self):
        user = self.create_user("profileadmin")
        Admin.objects.create(
            user=user,
            name="Profile Admin",
            email="admin@example.com",
            phone="555-0101",
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "secure-test-password"},
        )

        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 200)

    def test_admin_dashboard_requires_an_admin_role(self):
        self.create_user("teststudent")
        self.client.login(username="teststudent", password="secure-test-password")

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_admin_dashboard_displays_registered_students_and_question_count(self):
        user = self.create_user("dashboardadmin", is_staff=True)
        student_user = self.create_user("registeredstudent")
        Student.objects.create(
            user=student_user,
            name="Registered Student",
            email="registered@example.com",
            phone="555-0100",
        )
        subject = Subject.objects.create(name="Dashboard Test Subject")
        Question.objects.create(subject=subject, question_text="A dashboard question?")
        self.client.force_login(user)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registered students")
        self.assertContains(response, "Total questions")
        self.assertEqual(
            response.context["registered_student_count"],
            Student.objects.filter(user__isnull=False).count(),
        )
        self.assertEqual(response.context["question_count"], Question.objects.count())

    def test_admin_can_create_question_with_four_options_for_selected_subject(self):
        admin_user = self.create_user("questionadmin", is_staff=True)
        subject = Subject.objects.create(name="Question Form Subject")
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("question_create"),
            {
                "subject": subject.pk,
                "question_text": "Which number is even?",
                "explanation": "Even numbers are divisible by two.",
                "option_a": "3",
                "option_b": "5",
                "option_c": "8",
                "option_d": "9",
                "correct_option": "C",
            },
        )

        question = Question.objects.get(question_text="Which number is even?")
        self.assertRedirects(
            response,
            f"{reverse('question_create')}?subject={subject.pk}",
        )
        self.assertEqual(question.subject, subject)
        self.assertEqual(question.options.count(), 4)
        self.assertEqual(
            question.options.get(is_answer=True).option_text,
            "8",
        )

    def test_question_create_page_filters_questions_by_selected_subject(self):
        admin_user = self.create_user("questionviewer", is_staff=True)
        subject = Subject.objects.create(name="Filtered Question Subject")
        other_subject = Subject.objects.create(name="Other Question Subject")
        question = Question.objects.create(
            subject=subject,
            question_text="Question for the selected subject",
        )
        Question.objects.create(
            subject=other_subject,
            question_text="Question for another subject",
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("question_create"),
            {"subject": subject.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, question.question_text)
        self.assertNotContains(response, "Question for another subject")

    def test_admin_can_create_question_and_options_with_checkbox_answer(self):
        admin_user = self.create_user("questionformsetadmin", is_staff=True)
        subject = Subject.objects.create(name="Question Formset Subject")
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("question_create"),
            {
                "subject": subject.pk,
                "question_text": "Which one is correct?",
                "explanation": "A test explanation.",
                "options-TOTAL_FORMS": "4",
                "options-INITIAL_FORMS": "0",
                "options-MIN_NUM_FORMS": "0",
                "options-MAX_NUM_FORMS": "1000",
                "options-0-option_text": "Correct",
                "options-0-is_answer": "on",
                "options-1-option_text": "Incorrect",
                "options-2-option_text": "",
                "options-3-option_text": "",
            },
        )

        question = Question.objects.get(question_text="Which one is correct?")
        self.assertRedirects(
            response,
            f"{reverse('question_create')}?subject={subject.pk}",
        )
        self.assertEqual(question.options.count(), 2)
        self.assertEqual(
            question.options.get(is_answer=True).option_text,
            "Correct",
        )

    def test_admin_can_update_question_add_and_delete_options_then_delete_question(self):
        admin_user = self.create_user("questionupdateadmin", is_staff=True)
        subject = Subject.objects.create(name="Question Update Subject")
        question = Question.objects.create(
            subject=subject,
            question_text="Original question",
            explanation="Original explanation",
        )
        correct_option = Option.objects.create(
            question=question,
            option_text="Original answer",
            is_answer=True,
        )
        removable_option = Option.objects.create(
            question=question,
            option_text="Remove me",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("question_update", args=(question.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="checkbox"')

        response = self.client.post(
            reverse("question_update", args=(question.pk,)),
            {
                "subject": subject.pk,
                "question_text": "Updated question",
                "explanation": "Updated explanation",
                "options-TOTAL_FORMS": "3",
                "options-INITIAL_FORMS": "2",
                "options-MIN_NUM_FORMS": "0",
                "options-MAX_NUM_FORMS": "1000",
                "options-0-id": correct_option.pk,
                "options-0-question": question.pk,
                "options-0-option_text": "Updated answer",
                "options-0-is_answer": "on",
                "options-1-id": removable_option.pk,
                "options-1-question": question.pk,
                "options-1-option_text": "Remove me",
                "options-1-DELETE": "on",
                "options-2-option_text": "New distractor",
            },
        )

        question.refresh_from_db()
        self.assertRedirects(
            response,
            f"{reverse('question_create')}?subject={subject.pk}",
        )
        self.assertEqual(question.question_text, "Updated question")
        self.assertEqual(question.options.count(), 2)
        self.assertEqual(
            question.options.get(is_answer=True).option_text,
            "Updated answer",
        )
        self.assertTrue(
            question.options.filter(option_text="New distractor").exists()
        )

        response = self.client.post(
            reverse("question_delete", args=(question.pk,)),
        )
        self.assertRedirects(
            response,
            f"{reverse('question_create')}?subject={subject.pk}",
        )
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())
        self.assertFalse(Option.objects.filter(question_id=question.pk).exists())

    def test_students_cannot_create_questions(self):
        student_user = self.create_user("questionstudent")
        self.client.force_login(student_user)

        response = self.client.get(reverse("question_create"))

        self.assertEqual(response.status_code, 403)

    def test_dashboards_require_authentication(self):
        response = self.client.get(reverse("student_dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('student_dashboard')}",
        )

    def test_logout_uses_django_authentication(self):
        user = self.create_user("testadmin", is_staff=True)
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertRedirects(
            self.client.get(reverse("admin_dashboard")),
            f"{reverse('login')}?next={reverse('admin_dashboard')}",
        )

    def test_login_page_has_branded_form(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in to continue")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')


class ProfileAndCatalogTests(TestCase):
    def create_student(self):
        user = get_user_model().objects.create_user(
            username="student",
            password="secure-test-password",
        )
        student = Student.objects.create(
            user=user,
            name="Current Student",
            email="current@example.com",
            phone="555-0100",
        )
        return user, student

    def test_student_profile_view_shows_profile_and_edit_link(self):
        user, student = self.create_student()
        self.client.force_login(user)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, student.name)
        self.assertContains(response, reverse("student_profile_edit"))

    def test_student_profile_shows_request_status_and_timestamps(self):
        user, student = self.create_student()
        reviewed_at = timezone.now()
        change = StudentProfileChange.objects.create(
            student=student,
            name="Former Request",
            email="former@example.com",
            phone="555-0111",
            status=StudentProfileChange.Status.REJECTED,
            reviewed_at=reviewed_at,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, change.get_status_display())
        self.assertContains(response, change.created_at.strftime("%b"))
        self.assertContains(response, reviewed_at.strftime("%b"))
        self.assertContains(response, "Profile update requests")

    def test_profile_edit_form_starts_with_current_student_details(self):
        user, student = self.create_student()
        self.client.force_login(user)

        response = self.client.get(reverse("student_profile_edit"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{student.name}"')
        self.assertContains(response, f'value="{student.email}"')

    def test_admin_profile_view_uses_admin_record(self):
        user = get_user_model().objects.create_user(
            username="admin",
            password="secure-test-password",
            is_staff=True,
        )
        Admin.objects.create(
            user=user,
            name="Quizopedia Admin",
            email="admin@example.com",
            phone="555-0110",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quizopedia Admin")
        self.assertContains(response, "admin@example.com")

    def test_student_update_is_pending_until_admin_approves(self):
        user, student = self.create_student()
        self.client.force_login(user)

        response = self.client.post(
            reverse("student_profile_edit"),
            {
                "name": "Updated Student",
                "email": "updated@example.com",
                "phone": "555-0199",
            },
        )

        self.assertRedirects(response, reverse("profile"))
        student.refresh_from_db()
        self.assertEqual(student.name, "Current Student")
        change = StudentProfileChange.objects.get(student=student)
        self.assertEqual(change.status, StudentProfileChange.Status.PENDING)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_admin_approval_applies_profile_update_and_emails_student(self):
        _, student = self.create_student()
        change = StudentProfileChange.objects.create(
            student=student,
            name="Updated Student",
            email="updated@example.com",
            phone="555-0199",
        )
        admin_user = get_user_model().objects.create_user(
            username="reviewer",
            password="secure-test-password",
            is_staff=True,
        )
        self.client.force_login(admin_user)

        dashboard = self.client.get(reverse("admin_dashboard"))
        self.assertContains(dashboard, "Updated Student")
        self.assertContains(dashboard, "Approve")
        self.assertContains(dashboard, "Submitted")
        self.assertContains(dashboard, "Reviewed")
        self.assertContains(dashboard, change.created_at.strftime("%b"))

        response = self.client.post(
            reverse(
                "review_student_profile_change",
                args=(change.id, StudentProfileChange.Status.APPROVED),
            )
        )

        self.assertRedirects(
            response,
            reverse("admin_dashboard"),
            fetch_redirect_response=False,
        )
        student.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual(student.name, "Updated Student")
        self.assertEqual(student.email, "updated@example.com")
        self.assertEqual(change.status, StudentProfileChange.Status.APPROVED)
        self.assertIsNotNone(change.reviewed_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["updated@example.com"])
        self.assertIn("approved", mail.outbox[0].subject)
        self.assertContains(
            self.client.get(reverse("admin_dashboard")),
            "notification emailed",
        )

    def test_admin_dashboard_shows_resolved_request_status_and_review_time(self):
        _, student = self.create_student()
        reviewed_at = timezone.now()
        change = StudentProfileChange.objects.create(
            student=student,
            name="Rejected Student",
            email="rejected@example.com",
            phone="555-0199",
            status=StudentProfileChange.Status.REJECTED,
            reviewed_at=reviewed_at,
        )
        admin_user = get_user_model().objects.create_user(
            username="historyreviewer",
            password="secure-test-password",
            is_staff=True,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, change.get_status_display())
        self.assertContains(response, reviewed_at.strftime("%b"))
        self.assertNotContains(
            response,
            reverse(
                "review_student_profile_change",
                args=(change.id, StudentProfileChange.Status.APPROVED),
            ),
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_admin_rejection_does_not_change_student_profile_and_emails_student(self):
        _, student = self.create_student()
        change = StudentProfileChange.objects.create(
            student=student,
            name="Rejected Student",
            email="rejected@example.com",
            phone="555-0199",
        )
        admin_user = get_user_model().objects.create_user(
            username="reviewer",
            password="secure-test-password",
            is_staff=True,
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse(
                "review_student_profile_change",
                args=(change.id, StudentProfileChange.Status.REJECTED),
            )
        )

        student.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual(student.name, "Current Student")
        self.assertEqual(change.status, StudentProfileChange.Status.REJECTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [student.email])
        self.assertIn("rejected", mail.outbox[0].subject)
        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_admin_can_create_update_and_delete_subjects(self):
        admin_user = get_user_model().objects.create_user(
            username="subjectadmin",
            password="secure-test-password",
            is_staff=True,
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("subject_create"),
            {"name": "History", "description": "Past events and societies."},
        )
        self.assertRedirects(response, reverse("subject_list"))
        subject = Subject.objects.get(name="History")

        response = self.client.post(
            reverse("subject_update", args=(subject.pk,)),
            {"name": "World History", "description": "Global history."},
        )
        self.assertRedirects(response, reverse("subject_list"))
        subject.refresh_from_db()
        self.assertEqual(subject.name, "World History")
        self.assertEqual(subject.description, "Global history.")

        self.assertEqual(
            self.client.get(reverse("subject_delete", args=(subject.pk,))).status_code,
            200,
        )
        response = self.client.post(reverse("subject_delete", args=(subject.pk,)))
        self.assertRedirects(response, reverse("subject_list"))
        self.assertFalse(Subject.objects.filter(pk=subject.pk).exists())

    def test_students_cannot_manage_subjects_and_delete_requires_post(self):
        user, _ = self.create_student()
        subject = Subject.objects.create(name="Protected Subject")
        self.client.force_login(user)

        response = self.client.get(reverse("subject_list"))
        self.assertEqual(response.status_code, 403)

        admin_user = get_user_model().objects.create_user(
            username="subjectdeleteadmin",
            password="secure-test-password",
            is_staff=True,
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse("subject_delete", args=(subject.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Subject.objects.filter(pk=subject.pk).exists())

    def test_subject_list_searches_and_paginates(self):
        admin_user = get_user_model().objects.create_user(
            username="subjectpagination",
            password="secure-test-password",
            is_staff=True,
        )
        self.client.force_login(admin_user)
        for number in range(12):
            Subject.objects.create(
                name=f"Subject {number:02d}",
                description="Pagination category",
            )

        response = self.client.get(reverse("subject_list"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertLessEqual(len(response.context["subjects"]), 10)

        response = self.client.get(
            reverse("subject_list"),
            {"q": "Pagination"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subject 00")
        self.assertContains(response, "Subject 09")
        self.assertEqual(response.context["search_query"], "Pagination")

    def test_subject_form_rejects_duplicate_names_and_shows_errors(self):
        admin_user = get_user_model().objects.create_user(
            username="subjectvalidation",
            password="secure-test-password",
            is_staff=True,
        )
        Subject.objects.create(name="Validation Duplicate", description="Numbers")
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("subject_create"),
            {"name": " validation duplicate ", "description": "Duplicate"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A subject with this name already exists.")
        self.assertContains(response, "Please correct the errors below.")
        self.assertEqual(
            Subject.objects.filter(name__iexact="validation duplicate").count(),
            1,
        )

    def test_student_cannot_review_profile_change(self):
        user, student = self.create_student()
        change = StudentProfileChange.objects.create(
            student=student,
            name="Updated Student",
            email="updated@example.com",
            phone="555-0199",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse(
                "review_student_profile_change",
                args=(change.id, StudentProfileChange.Status.APPROVED),
            )
        )

        self.assertEqual(response.status_code, 403)
        change.refresh_from_db()
        self.assertEqual(change.status, StudentProfileChange.Status.PENDING)

    def test_subject_and_question_models_are_related(self):
        subject = Subject.objects.create(
            name="Catalog Test Mathematics",
            description="Numbers and problem solving.",
        )
        question = Question.objects.create(
            subject=subject,
            question_text="What is 2 + 2?",
        )
        answer = Option.objects.create(
            question=question,
            option_text="4",
            is_answer=True,
        )

        self.assertEqual(subject.questions.get(), question)
        self.assertEqual(question.options.get(), answer)
