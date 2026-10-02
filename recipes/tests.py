"""Automated tests for the TheCocktailDB client and the recipe views.

No test touches the real network: ``requests.get`` is replaced with a fake.
"""
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from bar.models import BarStock, Ingredient

from . import services

MARGARITA = {
    "idDrink": "11007",
    "strDrink": "Margarita",
    "strCategory": "Ordinary Drink",
    "strAlcoholic": "Alcoholic",
    "strGlass": "Cocktail glass",
    "strInstructions": "Shake with ice and strain.",
    "strDrinkThumb": "https://example.com/margarita.jpg",
    "strIngredient1": "Tequila",
    "strMeasure1": "1 1/2 oz ",
    "strIngredient2": "Triple sec",
    "strMeasure2": "1/2 oz ",
    "strIngredient3": "Lime juice",
    "strMeasure3": "1 oz ",
    "strIngredient4": "Salt",
    "strMeasure4": None,
    "strIngredient5": None,
    "strMeasure5": None,
}


def fake_response(payload, status_error=None):
    """Build a stand-in for a requests.Response returning ``payload``."""
    response = MagicMock()
    response.json.return_value = payload
    if status_error:
        response.raise_for_status.side_effect = status_error
    return response


class ParseDrinkTests(TestCase):
    """parse_drink flattens the API's numbered ingredient fields."""

    def test_collects_ingredients_in_order_and_skips_nulls(self):
        drink = services.parse_drink(MARGARITA)
        self.assertEqual(drink["id"], 11007)
        self.assertEqual([i["name"] for i in drink["ingredients"]], ["Tequila", "Triple sec", "Lime juice", "Salt"])

    def test_strips_measures_and_handles_missing_measure(self):
        ingredients = services.parse_drink(MARGARITA)["ingredients"]
        self.assertEqual(ingredients[0]["measure"], "1 1/2 oz")
        self.assertEqual(ingredients[3]["measure"], "")

    def test_missing_optional_fields_default_to_empty(self):
        drink = services.parse_drink({"idDrink": "1"})
        self.assertEqual(drink["name"], "Unnamed cocktail")
        self.assertEqual(drink["ingredients"], [])


class ServiceTests(TestCase):
    """search_cocktails and get_cocktail."""

    def setUp(self):
        cache.clear()

    @patch("recipes.services.requests.get")
    def test_search_returns_parsed_drinks(self, mock_get):
        mock_get.return_value = fake_response({"drinks": [MARGARITA]})
        results = services.search_cocktails("margarita")
        self.assertEqual(results[0]["name"], "Margarita")
        self.assertEqual(mock_get.call_args.kwargs["params"], {"s": "margarita"})

    @patch("recipes.services.requests.get")
    def test_search_with_no_matches_returns_empty_list(self, mock_get):
        mock_get.return_value = fake_response({"drinks": None})
        self.assertEqual(services.search_cocktails("zzzz"), [])

    @patch("recipes.services.requests.get")
    def test_blank_search_makes_no_request(self, mock_get):
        self.assertEqual(services.search_cocktails("   "), [])
        mock_get.assert_not_called()

    @patch("recipes.services.requests.get")
    def test_responses_are_cached(self, mock_get):
        mock_get.return_value = fake_response({"drinks": [MARGARITA]})
        services.search_cocktails("margarita")
        services.search_cocktails("margarita")
        self.assertEqual(mock_get.call_count, 1)

    @patch("recipes.services.requests.get")
    def test_get_cocktail_unknown_id_returns_none(self, mock_get):
        mock_get.return_value = fake_response({"drinks": None})
        self.assertIsNone(services.get_cocktail(1))

    @patch("recipes.services.requests.get", side_effect=requests.ConnectionError("down"))
    def test_network_failure_raises_api_error(self, _mock_get):
        with self.assertRaises(services.CocktailAPIError):
            services.search_cocktails("margarita")

    @patch("recipes.services.requests.get")
    def test_http_error_raises_api_error(self, mock_get):
        mock_get.return_value = fake_response({}, status_error=requests.HTTPError("500"))
        with self.assertRaises(services.CocktailAPIError):
            services.get_cocktail(1)

    @patch("recipes.services.requests.get")
    def test_invalid_json_raises_api_error(self, mock_get):
        response = fake_response({})
        response.json.side_effect = ValueError("not json")
        mock_get.return_value = response
        with self.assertRaises(services.CocktailAPIError):
            services.get_cocktail(1)


class BrowseViewTests(TestCase):
    """The public search page."""

    def setUp(self):
        cache.clear()

    def test_page_is_public_and_shows_suggestions_without_query(self):
        response = self.client.get(reverse("recipes:browse"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Negroni")

    @patch("recipes.services.requests.get")
    def test_search_shows_results(self, mock_get):
        mock_get.return_value = fake_response({"drinks": [MARGARITA]})
        response = self.client.get(reverse("recipes:browse"), {"q": "margarita"})
        self.assertContains(response, "Margarita")
        self.assertContains(response, reverse("recipes:detail", args=[11007]))

    @patch("recipes.services.requests.get")
    def test_search_with_no_results_says_so(self, mock_get):
        mock_get.return_value = fake_response({"drinks": None})
        response = self.client.get(reverse("recipes:browse"), {"q": "zzzz"})
        self.assertContains(response, "No cocktails found")

    @patch("recipes.services.requests.get", side_effect=requests.ConnectionError("down"))
    def test_api_failure_shows_friendly_message(self, _mock_get):
        response = self.client.get(reverse("recipes:browse"), {"q": "margarita"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not responding")


class DetailViewTests(TestCase):
    """The recipe detail page."""

    def setUp(self):
        cache.clear()
        self.url = reverse("recipes:detail", args=[11007])

    @patch("recipes.services.requests.get")
    def test_guest_sees_recipe_and_login_hint(self, mock_get):
        mock_get.return_value = fake_response({"drinks": [MARGARITA]})
        response = self.client.get(self.url)
        self.assertContains(response, "Shake with ice and strain.")
        self.assertContains(response, "Lime juice")
        self.assertContains(response, "to see which ingredients you already have")
        self.assertNotContains(response, "In your bar")

    @patch("recipes.services.requests.get")
    def test_logged_in_user_sees_stock_badges(self, mock_get):
        mock_get.return_value = fake_response({"drinks": [MARGARITA]})
        user = User.objects.create_user(email="a@example.com", password="a-Strong-pass-2026", first_name="A")
        BarStock.objects.create(user=user, ingredient=Ingredient.objects.create(name="tequila"), quantity=1)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertContains(response, "In your bar", count=1)  # only the tequila (matched ignoring case)
        self.assertContains(response, "Not in stock", count=3)

    @patch("recipes.services.requests.get")
    def test_unknown_recipe_is_404(self, mock_get):
        mock_get.return_value = fake_response({"drinks": None})
        self.assertEqual(self.client.get(self.url).status_code, 404)

    @patch("recipes.services.requests.get", side_effect=requests.ConnectionError("down"))
    def test_api_failure_returns_503_page(self, _mock_get):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "not responding", status_code=503)
