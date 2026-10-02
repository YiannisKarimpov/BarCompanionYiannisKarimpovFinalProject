"""Automated tests for the public home page and the protected dashboard."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class HomeViewTests(TestCase):
    """The landing page is public."""

    def test_home_is_public(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bar Companion")

    def test_home_shows_signup_to_guests(self):
        self.assertContains(self.client.get(reverse("core:home")), "Create a free account")


class DashboardViewTests(TestCase):
    """The dashboard requires a logged-in user."""

    def test_guest_is_redirected_to_login(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('core:dashboard')}")

    def test_logged_in_user_sees_dashboard(self):
        user = User.objects.create_user(email="d@example.com", password="a-Strong-pass-2026", first_name="Dee")
        self.client.force_login(user)
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back, Dee")
