from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Admin, Student


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
