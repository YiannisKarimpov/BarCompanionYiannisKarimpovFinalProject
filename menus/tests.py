"""Tests for the menu builder: margin maths, forms, views and ownership."""
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from recipes import services

from .forms import MenuForm, MenuItemForm
from .models import Menu, MenuItem

DRINK = {"id": 11007, "name": "Margarita", "category": "", "alcoholic": "", "glass": "",
         "instructions": "Shake.", "thumb": "https://example.com/m.jpg", "ingredients": []}


def make_user(email="a@example.com"):
    return User.objects.create_user(email=email, password="a-Strong-pass-2026", first_name="Test")


def make_item(menu, drink_id=1, cost="2", price="10", name="Drink"):
    return MenuItem.objects.create(menu=menu, drink_id=drink_id, name=name, cost=Decimal(cost), price=Decimal(price))


class MarginTests(TestCase):
    def setUp(self):
        self.menu = Menu.objects.create(user=make_user(), name="Summer")

    def test_margin_and_percent(self):
        item = make_item(self.menu, cost="2.50", price="10.00")
        self.assertEqual(item.margin, Decimal("7.50"))
        self.assertEqual(item.margin_percent, Decimal("75.0"))

    def test_no_percent_without_a_price(self):
        item = make_item(self.menu, cost="2", price="0")
        self.assertIsNone(item.margin_percent)

    def test_loss_making_item_has_negative_margin(self):
        item = make_item(self.menu, cost="12", price="10")
        self.assertEqual(item.margin, Decimal("-2"))
        self.assertEqual(item.margin_percent, Decimal("-20.0"))

    def test_average_margin_ignores_unpriced_items(self):
        make_item(self.menu, 1, cost="2", price="10")   # 80%
        make_item(self.menu, 2, cost="5", price="10")   # 50%
        make_item(self.menu, 3, cost="1", price="0")    # unpriced
        self.assertEqual(self.menu.average_margin_percent(), Decimal("65.0"))

    def test_average_margin_none_for_empty_menu(self):
        self.assertIsNone(self.menu.average_margin_percent())

    def test_constraints(self):
        user = self.menu.user
        with self.assertRaises(IntegrityError), transaction.atomic():
            Menu.objects.create(user=user, name="Summer")
        make_item(self.menu, 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_item(self.menu, 1)
        Menu.objects.create(user=make_user("b@example.com"), name="Summer")  # other user: fine


class FormTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_menu_name_unique_per_user_ignoring_case(self):
        Menu.objects.create(user=self.user, name="Summer")
        self.assertFalse(MenuForm({"name": " summer "}, user=self.user).is_valid())
        self.assertTrue(MenuForm({"name": "summer"}, user=make_user("b@example.com")).is_valid())

    def test_item_form_rejects_negative_values(self):
        self.assertFalse(MenuItemForm({"cost": "-1", "price": "5"}).is_valid())
        self.assertFalse(MenuItemForm({"cost": "1", "price": "-5"}).is_valid())
        self.assertTrue(MenuItemForm({"cost": "1.20", "price": "9.50"}).is_valid())


class ViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.menu = Menu.objects.create(user=self.user, name="Summer")

    def test_login_required_everywhere(self):
        self.client.logout()
        item = make_item(self.menu)
        urls = [reverse("menus:list"), reverse("menus:create"), reverse("menus:detail", args=[self.menu.pk]),
                reverse("menus:delete", args=[self.menu.pk]), reverse("menus:edit_item", args=[item.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        for url in (reverse("menus:add_item", args=[1]), reverse("menus:remove_item", args=[item.pk])):
            self.assertEqual(self.client.post(url).status_code, 302, url)
        self.assertTrue(MenuItem.objects.filter(pk=item.pk).exists())

    def test_create_menu(self):
        response = self.client.post(reverse("menus:create"), {"name": "Winter"})
        menu = Menu.objects.get(name="Winter")
        self.assertEqual(menu.user, self.user)
        self.assertRedirects(response, reverse("menus:detail", args=[menu.pk]))

    def test_list_shows_only_own_menus(self):
        Menu.objects.create(user=make_user("b@example.com"), name="Secret")
        response = self.client.get(reverse("menus:list"))
        self.assertContains(response, "Summer")
        self.assertNotContains(response, "Secret")

    def test_detail_shows_totals(self):
        make_item(self.menu, 1, cost="2", price="10", name="Margarita")
        make_item(self.menu, 2, name="Unpriced", cost="1", price="0")
        response = self.client.get(reverse("menus:detail", args=[self.menu.pk]))
        self.assertContains(response, "Margarita")
        self.assertContains(response, "80.0%")
        self.assertContains(response, "still needs a price")

    def test_cannot_see_edit_or_delete_another_users_menu(self):
        other = Menu.objects.create(user=make_user("b@example.com"), name="Theirs")
        item = make_item(other)
        self.assertEqual(self.client.get(reverse("menus:detail", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("menus:delete", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("menus:edit_item", args=[item.pk]), {"cost": 1, "price": 2}).status_code, 404)
        self.assertEqual(self.client.post(reverse("menus:remove_item", args=[item.pk])).status_code, 404)
        self.assertTrue(Menu.objects.filter(pk=other.pk).exists())
        self.assertTrue(MenuItem.objects.filter(pk=item.pk).exists())

    @patch("menus.views.services.get_cocktail", return_value=DRINK)
    def test_add_item_copies_name_and_thumb(self, _get):
        self.client.post(reverse("menus:add_item", args=[11007]), {"menu": self.menu.pk})
        item = MenuItem.objects.get()
        self.assertEqual((item.menu, item.drink_id, item.name, item.cost, item.price),
                         (self.menu, 11007, "Margarita", 0, 0))

    @patch("menus.views.services.get_cocktail", return_value=DRINK)
    def test_adding_twice_does_not_duplicate(self, _get):
        url = reverse("menus:add_item", args=[11007])
        self.client.post(url, {"menu": self.menu.pk})
        response = self.client.post(url, {"menu": self.menu.pk}, follow=True)
        self.assertEqual(MenuItem.objects.count(), 1)
        self.assertContains(response, "already on")

    @patch("menus.views.services.get_cocktail", return_value=DRINK)
    def test_cannot_add_to_another_users_menu(self, _get):
        other = Menu.objects.create(user=make_user("b@example.com"), name="Theirs")
        response = self.client.post(reverse("menus:add_item", args=[11007]), {"menu": other.pk})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(MenuItem.objects.count(), 0)

    @patch("menus.views.services.get_cocktail", return_value=None)
    def test_unknown_drink_404(self, _get):
        self.assertEqual(self.client.post(reverse("menus:add_item", args=[1]), {"menu": self.menu.pk}).status_code, 404)

    @patch("menus.views.services.get_cocktail", side_effect=services.CocktailAPIError("down"))
    def test_api_down_is_404_not_a_crash(self, _get):
        self.assertEqual(self.client.post(reverse("menus:add_item", args=[1]), {"menu": self.menu.pk}).status_code, 404)

    def test_missing_menu_field_is_404(self):
        self.assertEqual(self.client.post(reverse("menus:add_item", args=[1])).status_code, 404)

    def test_set_prices_and_remove(self):
        item = make_item(self.menu, cost="0", price="0")
        self.client.post(reverse("menus:edit_item", args=[item.pk]), {"cost": "1.50", "price": "9"})
        item.refresh_from_db()
        self.assertEqual((item.cost, item.price), (Decimal("1.50"), Decimal("9.00")))
        self.client.post(reverse("menus:remove_item", args=[item.pk]))
        self.assertFalse(MenuItem.objects.exists())

    def test_delete_menu_removes_its_items(self):
        make_item(self.menu)
        self.client.post(reverse("menus:delete", args=[self.menu.pk]))
        self.assertFalse(Menu.objects.exists())
        self.assertFalse(MenuItem.objects.exists())

    def test_remove_requires_post(self):
        item = make_item(self.menu)
        self.assertEqual(self.client.get(reverse("menus:remove_item", args=[item.pk])).status_code, 405)


class RecipePageTests(TestCase):
    @patch("recipes.views.services.get_cocktail", return_value=DRINK)
    def test_recipe_page_offers_menus(self, _get):
        user = make_user()
        self.client.force_login(user)
        url = reverse("recipes:detail", args=[11007])
        self.assertContains(self.client.get(url), "Create a menu")
        Menu.objects.create(user=user, name="Summer")
        response = self.client.get(url)
        self.assertContains(response, "Add to menu")
        self.assertContains(response, "Summer")

    @patch("recipes.views.services.get_cocktail", return_value=DRINK)
    def test_guest_sees_no_menu_controls(self, _get):
        response = self.client.get(reverse("recipes:detail", args=[11007]))
        self.assertNotContains(response, "Add to menu")
        self.assertNotContains(response, "Create a menu")
