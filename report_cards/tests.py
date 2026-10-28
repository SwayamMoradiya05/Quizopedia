from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationTests(TestCase):
    def test_login_uses_django_authentication(self):
        user = get_user_model().objects.create_user(
            username="testuser",
            password="secure-test-password",
            is_staff=True,
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "secure-test-password"},
        )

        self.assertRedirects(response, reverse("admin:index"))
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_logout_uses_django_authentication(self):
        user = get_user_model().objects.create_user(
            username="testuser",
            password="secure-test-password",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_admin_requires_authentication(self):
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)
