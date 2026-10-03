"""Automated tests for the "Can I make it?" matcher (no real network calls)."""
from io import StringIO
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User
from bar.models import BarStock, Ingredient

from . import matching, services


def drink(drink_id, name, ingredients):
    """A raw API drink with the given ingredient names."""
    raw = {"idDrink": str(drink_id), "strDrink": name, "strDrinkThumb": ""}
    for number, ingredient in enumerate(ingredients, start=1):
        raw[f"strIngredient{number}"] = ingredient
    return raw


DRINKS = {
    1: drink(1, "Daiquiri", ["Light rum", "Lime juice", "Sugar", "Ice"]),
    2: drink(2, "Mojito", ["Light rum", "Lime", "Mint", "Sugar", "Soda water"]),
    3: drink(3, "Gin Fizz", ["Gin", "Lemon juice", "Sugar", "Soda water"]),
    4: drink(4, "Dark and Stormy", ["Dark rum", "Ginger beer", "Lime", "Bitters"]),
    5: drink(5, "Mystery", ["Unobtainium", "Ice"]),
    6: drink(6, "Blue Agave", ["Tequila", "Blue Curacao"]),
}
NOT_IN_LETTER_LISTS = {6}  # only reachable through the category/glass top-up


def fake_get(url, params=None, timeout=None):
    """Stand-in for requests.get serving a small fake TheCocktailDB."""
    response = MagicMock()
    response.text = "x"
    if url.endswith("search.php"):
        letter = params["f"]
        matches = [
            raw for i, raw in DRINKS.items()
            if raw["strDrink"][0].lower() == letter and i not in NOT_IN_LETTER_LISTS
        ]
        payload = {"drinks": matches or None}
    elif url.endswith("list.php"):
        payload = {"drinks": [{"strCategory": "Ordinary Drink"}] if "c" in params else [{"strGlass": "Cocktail glass"}]}
    elif url.endswith("filter.php"):
        payload = {"drinks": [{"idDrink": str(i)} for i in DRINKS]}
    elif url.endswith("lookup.php"):
        payload = {"drinks": [DRINKS[int(params["i"])]]}
    else:
        raise AssertionError(f"unexpected URL {url}")
    response.json.return_value = payload
    return response


def only_letter_lists_work(url, params=None, timeout=None):
    """requests.get stand-in where everything except the by-letter lists fails."""
    if url.endswith("search.php"):
        return fake_get(url, params, timeout)
    raise requests.ConnectionError("down")


class NameMatchingTests(SimpleTestCase):
    """names_match and is_staple."""

    def test_ignores_case_and_matches_whole_words(self):
        self.assertTrue(matching.names_match("RUM", "rum"))
        self.assertTrue(matching.names_match("Rum", "Light rum"))
        self.assertTrue(matching.names_match("Dry vermouth", "Vermouth"))

    def test_gin_does_not_match_ginger_ale(self):
        self.assertFalse(matching.names_match("Gin", "Ginger ale"))

    def test_plurals_match(self):
        self.assertTrue(matching.names_match("Limes", "Lime"))

    def test_unrelated_and_blank_names_do_not_match(self):
        self.assertFalse(matching.names_match("Vodka", "Tequila"))
        self.assertFalse(matching.names_match("", "Tequila"))

    def test_ice_and_water_are_staples(self):
        self.assertTrue(matching.is_staple("Crushed ice"))
        self.assertTrue(matching.is_staple("Water"))
        self.assertFalse(matching.is_staple("Soda water"))


class CatalogueServiceTests(TestCase):
    """services.cocktails_starting_with."""

    def setUp(self):
        cache.clear()

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_returns_parsed_drinks_for_the_letter(self, mock_get):
        results = services.cocktails_starting_with("d")
        self.assertEqual(sorted(r["name"] for r in results), ["Daiquiri", "Dark and Stormy"])
        self.assertEqual(mock_get.call_args.kwargs["params"], {"f": "d"})
        self.assertEqual(results[0]["ingredients"][0]["name"], "Light rum")

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_letter_with_no_drinks_gives_empty_list(self, _mock_get):
        self.assertEqual(services.cocktails_starting_with("z"), [])

    @patch("recipes.services.requests.get")
    def test_empty_response_body_gives_empty_list(self, mock_get):
        response = MagicMock()
        response.text = "  "
        mock_get.return_value = response
        self.assertEqual(services.cocktails_starting_with("q"), [])

    @patch("recipes.services.requests.get")
    def test_blank_letter_makes_no_request(self, mock_get):
        self.assertEqual(services.cocktails_starting_with("  "), [])
        mock_get.assert_not_called()


class FindMatchesTests(TestCase):
    """matching.find_matches splits recipes into ready and one-away."""

    def setUp(self):
        cache.clear()

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_ready_cocktail_is_found(self, _mock_get):
        # Ice is a staple, so rum, lime juice and sugar cover the Daiquiri.
        result = matching.find_matches(["Rum", "Lime juice", "Sugar"])
        self.assertEqual([d["name"] for d in result["ready"]], ["Daiquiri"])
        self.assertEqual(result["almost"], [])

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_one_missing_ingredient_is_reported(self, _mock_get):
        result = matching.find_matches(["Rum", "Lime", "Sugar", "Soda water"])
        self.assertEqual([d["name"] for d in result["almost"]], ["Mojito"])
        self.assertEqual(result["almost"][0]["missing"], ["Mint"])

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_recipes_two_or_more_short_are_left_out(self, _mock_get):
        result = matching.find_matches(["Rum"])
        names = [d["name"] for d in result["ready"] + result["almost"]]
        self.assertNotIn("Dark and Stormy", names)

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_almost_needs_at_least_one_ingredient_in_stock(self, _mock_get):
        # "Mystery" has one real ingredient, so with nothing matching it is not "almost".
        result = matching.find_matches(["Rum"])
        self.assertNotIn("Mystery", [d["name"] for d in result["almost"]])

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_two_missing_ingredients_are_listed_as_close(self, _mock_get):
        result = matching.find_matches(["Rum"])
        daiquiri = next(d for d in result["close"] if d["name"] == "Daiquiri")
        self.assertEqual(daiquiri["missing"], ["Lime juice", "Sugar"])
        self.assertEqual(result["checked"], len(DRINKS))

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_blank_and_duplicate_stock_names_are_ignored(self, _mock_get):
        result = matching.find_matches(["Rum", "Rum", "", "Lime juice", "Sugar"])
        self.assertEqual([d["name"] for d in result["ready"]], ["Daiquiri"])

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_catalogue_is_loaded_once_then_cached(self, mock_get):
        matching.find_matches(["Rum"])
        first_calls = mock_get.call_count
        matching.find_matches(["Gin"])
        self.assertGreater(first_calls, len(matching.CATALOGUE_LETTERS))
        self.assertEqual(mock_get.call_count, first_calls)

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_drinks_missing_from_letter_lists_are_added_from_categories(self, _mock_get):
        # "Blue Agave" is not in any by-letter list, only in the category/glass top-up.
        result = matching.find_matches(["Tequila", "Blue Curacao"])
        self.assertEqual([d["name"] for d in result["ready"]], ["Blue Agave"])
        self.assertFalse(result["incomplete"])

    @patch("recipes.services.requests.get", side_effect=only_letter_lists_work)
    def test_top_up_failure_still_returns_letter_list_results(self, _mock_get):
        result = matching.find_matches(["Rum", "Lime juice", "Sugar"])
        self.assertEqual([d["name"] for d in result["ready"]], ["Daiquiri"])
        self.assertEqual(result["checked"], len(DRINKS) - len(NOT_IN_LETTER_LISTS))
        self.assertTrue(result["incomplete"])

    @patch("recipes.services.requests.get", side_effect=requests.ConnectionError("down"))
    def test_api_failure_raises(self, _mock_get):
        with self.assertRaises(services.CocktailAPIError):
            matching.find_matches(["Rum"])


class MatcherViewTests(TestCase):
    """The /recipes/can-i-make-it/ page."""

    def setUp(self):
        cache.clear()
        self.url = reverse("recipes:matcher")
        self.user = User.objects.create_user(email="m@example.com", password="a-Strong-pass-2026", first_name="Mo")

    def stock(self, *names):
        for name in names:
            BarStock.objects.create(user=self.user, ingredient=Ingredient.objects.create(name=name), quantity=1)

    def test_guest_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_empty_bar_prompts_to_add_stock(self):
        self.client.force_login(self.user)
        with patch("recipes.services.requests.get") as mock_get:
            response = self.client.get(self.url)
        self.assertContains(response, "Your bar is empty")
        mock_get.assert_not_called()

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_lists_ready_and_almost_cocktails(self, _mock_get):
        self.stock("Rum", "Lime", "Sugar", "Soda water", "Lime juice")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Daiquiri")
        self.assertContains(response, "Mojito")
        self.assertContains(response, "Missing: Mint")

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_only_own_stock_is_used(self, _mock_get):
        other = User.objects.create_user(email="o@example.com", password="a-Strong-pass-2026", first_name="O")
        BarStock.objects.create(user=other, ingredient=Ingredient.objects.create(name="Rum"), quantity=1)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.url), "Your bar is empty")

    @patch("recipes.services.requests.get", side_effect=requests.ConnectionError("down"))
    def test_api_failure_shows_friendly_message(self, _mock_get):
        self.stock("Rum")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not responding")

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_page_shows_which_bar_items_are_used(self, _mock_get):
        self.stock("Rum", "Sugar")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Using 2 items from your bar")
        self.assertContains(response, "Compared with 6 cocktails")
        self.assertContains(response, "Two ingredients away")

    @patch("recipes.services.requests.get", side_effect=only_letter_lists_work)
    def test_page_warns_when_some_requests_failed(self, _mock_get):
        self.stock("Rum")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.url), "may be incomplete")


class WarmCatalogueCommandTests(TestCase):
    """manage.py warm_catalogue fills the cache."""

    def setUp(self):
        cache.clear()

    @patch("recipes.services.requests.get", side_effect=fake_get)
    def test_command_caches_the_catalogue(self, mock_get):
        out = StringIO()
        call_command("warm_catalogue", stdout=out)
        self.assertIn(f"Cached {len(DRINKS)} cocktails", out.getvalue())
        calls_after_warm = mock_get.call_count
        matching.find_matches(["Rum"])  # served from the cache, no new requests
        self.assertEqual(mock_get.call_count, calls_after_warm)

    @patch("recipes.services.requests.get", side_effect=requests.ConnectionError("down"))
    def test_command_reports_an_unreachable_api(self, _mock_get):
        err = StringIO()
        call_command("warm_catalogue", stderr=err)
        self.assertIn("Could not reach", err.getvalue())
