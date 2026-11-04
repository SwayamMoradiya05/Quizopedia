from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Admin, Option, Question, Student, StudentProfileChange, Subject


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

        self.assertRedirects(response, reverse("student_dashboard"))
        dashboard = self.client.get(reverse("student_dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Test Student")

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

    def test_admin_approval_applies_profile_update(self):
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

        response = self.client.post(
            reverse(
                "review_student_profile_change",
                args=(change.id, StudentProfileChange.Status.APPROVED),
            )
        )

        self.assertRedirects(response, reverse("admin_dashboard"))
        student.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual(student.name, "Updated Student")
        self.assertEqual(student.email, "updated@example.com")
        self.assertEqual(change.status, StudentProfileChange.Status.APPROVED)
        self.assertIsNotNone(change.reviewed_at)

    def test_admin_rejection_does_not_change_student_profile(self):
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

        self.client.post(
            reverse(
                "review_student_profile_change",
                args=(change.id, StudentProfileChange.Status.REJECTED),
            )
        )

        student.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual(student.name, "Current Student")
        self.assertEqual(change.status, StudentProfileChange.Status.REJECTED)

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
