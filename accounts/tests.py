"""Automated tests for registration, login and logout (Django TestCase / unittest)."""
from django.test import TestCase
from django.urls import reverse

from .models import User


class UserModelTests(TestCase):
    """Tests for the custom email-based user model."""

    def test_create_user_hashes_password(self):
        user = User.objects.create_user(email="a@example.com", password="s3cret-pass!", first_name="Ann")
        self.assertNotEqual(user.password, "s3cret-pass!")
        self.assertTrue(user.check_password("s3cret-pass!"))

    def test_default_role_is_bartender(self):
        user = User.objects.create_user(email="b@example.com", password="s3cret-pass!")
        self.assertEqual(user.role, User.Role.BARTENDER)
        self.assertFalse(user.is_admin_role)

    def test_superuser_has_admin_role(self):
        admin = User.objects.create_superuser(email="root@example.com", password="s3cret-pass!")
        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertTrue(admin.is_admin_role)

    def test_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="s3cret-pass!")


class RegistrationTests(TestCase):
    """Tests for the sign-up flow."""

    def setUp(self):
        self.url = reverse("accounts:register")
        self.valid = {
            "first_name": "Yiannis",
            "email": "yiannis@example.com",
            "password1": "a-Strong-pass-2026",
            "password2": "a-Strong-pass-2026",
        }

    def test_register_page_loads(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_valid_registration_creates_user_and_logs_in(self):
        response = self.client.post(self.url, self.valid)
        self.assertRedirects(response, reverse("core:dashboard"))
        user = User.objects.get(email="yiannis@example.com")
        self.assertEqual(user.first_name, "Yiannis")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_mismatched_passwords_rejected(self):
        data = {**self.valid, "password2": "different-pass-2026"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="yiannis@example.com").exists())

    def test_duplicate_email_rejected(self):
        User.objects.create_user(email="yiannis@example.com", password="x-Strong-pass-1")
        response = self.client.post(self.url, self.valid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email="yiannis@example.com").count(), 1)


class LoginLogoutTests(TestCase):
    """Tests for logging in and out."""

    def setUp(self):
        self.user = User.objects.create_user(email="bar@example.com", password="a-Strong-pass-2026", first_name="Bar")

    def test_login_with_valid_credentials(self):
        response = self.client.post(reverse("accounts:login"), {"username": "bar@example.com", "password": "a-Strong-pass-2026"})
        self.assertRedirects(response, reverse("core:dashboard"))

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(reverse("accounts:login"), {"username": "bar@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_ends_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)
