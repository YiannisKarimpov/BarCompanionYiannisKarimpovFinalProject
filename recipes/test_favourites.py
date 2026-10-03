"""Tests for saving and removing favourite recipes."""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from . import services
from .models import Favourite

DRINK = {"id": 11007, "name": "Margarita", "category": "", "alcoholic": "", "glass": "",
         "instructions": "Shake.", "thumb": "https://example.com/m.jpg", "ingredients": []}


def make_user(email="a@example.com"):
    return User.objects.create_user(email=email, password="pass12345", first_name="Ann", last_name="Lee")


class FavouriteTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("recipes:toggle_favourite", args=[11007])

    @patch("recipes.views.services.get_cocktail", return_value=DRINK)
    def test_toggle_saves_then_removes(self, _get):
        self.client.post(self.url)
        fav = Favourite.objects.get()
        self.assertEqual((fav.user, fav.drink_id, fav.name), (self.user, 11007, "Margarita"))
        self.client.post(self.url)
        self.assertEqual(Favourite.objects.count(), 0)

    @patch("recipes.views.services.get_cocktail", return_value=DRINK)
    def test_toggle_redirects_to_recipe_by_default(self, _get):
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("recipes:detail", args=[11007]), fetch_redirect_response=False)

    @patch("recipes.views.services.get_cocktail", return_value=DRINK)
    def test_toggle_honours_safe_next_only(self, _get):
        response = self.client.post(self.url, {"next": reverse("recipes:favourites")})
        self.assertRedirects(response, reverse("recipes:favourites"), fetch_redirect_response=False)
        response = self.client.post(self.url, {"next": "https://evil.example.com/"})
        self.assertRedirects(response, reverse("recipes:detail", args=[11007]), fetch_redirect_response=False)

    def test_removing_needs_no_api_call(self):
        Favourite.objects.create(user=self.user, drink_id=11007, name="Margarita")
        with patch("recipes.views.services.get_cocktail", side_effect=AssertionError("no API call")):
            self.client.post(self.url)
        self.assertEqual(Favourite.objects.count(), 0)

    @patch("recipes.views.services.get_cocktail", return_value=None)
    def test_unknown_drink_is_404_and_not_saved(self, _get):
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertEqual(Favourite.objects.count(), 0)

    @patch("recipes.views.services.get_cocktail", side_effect=services.CocktailAPIError("down"))
    def test_api_down_when_saving_is_404_not_a_crash(self, _get):
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertEqual(self.client.get(reverse("recipes:favourites")).status_code, 302)
        self.assertEqual(Favourite.objects.count(), 0)

    def test_one_per_user_and_drink(self):
        from django.db import IntegrityError, transaction
        Favourite.objects.create(user=self.user, drink_id=1, name="X")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Favourite.objects.create(user=self.user, drink_id=1, name="X")
        Favourite.objects.create(user=make_user("b@example.com"), drink_id=1, name="X")


class FavouritePagesTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_list_shows_only_own_favourites(self):
        Favourite.objects.create(user=self.user, drink_id=1, name="Mine")
        Favourite.objects.create(user=make_user("b@example.com"), drink_id=2, name="Theirs")
        response = self.client.get(reverse("recipes:favourites"))
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Theirs")

    def test_empty_list_message(self):
        self.assertContains(self.client.get(reverse("recipes:favourites")), "not saved any recipes")

    def test_dashboard_shows_favourites(self):
        Favourite.objects.create(user=self.user, drink_id=1, name="Negroni")
        self.assertContains(self.client.get(reverse("core:dashboard")), "Negroni")

    @patch("recipes.views.services.get_cocktail", return_value=DRINK)
    def test_detail_button_reflects_state(self, _get):
        url = reverse("recipes:detail", args=[11007])
        self.assertContains(self.client.get(url), "Save")
        Favourite.objects.create(user=self.user, drink_id=11007, name="Margarita")
        self.assertContains(self.client.get(url), "Saved")

    @patch("recipes.views.services.get_cocktail", return_value=DRINK)
    def test_detail_hides_button_when_logged_out(self, _get):
        self.client.logout()
        response = self.client.get(reverse("recipes:detail", args=[11007]))
        self.assertNotContains(response, reverse("recipes:toggle_favourite", args=[11007]))
