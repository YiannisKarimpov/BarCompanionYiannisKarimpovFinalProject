"""Automated tests for the My bar models, form and views."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .forms import BarStockForm
from .models import BarStock, Ingredient


def make_user(email="a@example.com"):
    """Create a bartender account for tests."""
    return User.objects.create_user(email=email, password="a-Strong-pass-2026", first_name="Test")


class ModelTests(TestCase):
    """Tests for Ingredient and BarStock."""

    def test_ingredient_names_are_unique_ignoring_case(self):
        Ingredient.objects.create(name="Gin")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ingredient.objects.create(name="gin")

    def test_user_cannot_hold_same_ingredient_twice(self):
        user, gin = make_user(), Ingredient.objects.create(name="Gin")
        BarStock.objects.create(user=user, ingredient=gin, quantity=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BarStock.objects.create(user=user, ingredient=gin, quantity=2)

    def test_two_users_can_hold_same_ingredient(self):
        gin = Ingredient.objects.create(name="Gin")
        BarStock.objects.create(user=make_user("a@example.com"), ingredient=gin, quantity=1)
        BarStock.objects.create(user=make_user("b@example.com"), ingredient=gin, quantity=3)
        self.assertEqual(BarStock.objects.count(), 2)

    def test_str(self):
        item = BarStock(user=make_user(), ingredient=Ingredient(name="Rum"), quantity=Decimal("2"), unit="bottles")
        self.assertEqual(str(item), "Rum: 2 bottles")


class FormTests(TestCase):
    """Tests for BarStockForm."""

    def setUp(self):
        self.user = make_user()

    def test_creates_ingredient_and_stock(self):
        form = BarStockForm({"ingredient_name": "Dry   Vermouth ", "quantity": "1.5", "unit": "bottles"}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertEqual(item.ingredient.name, "Dry Vermouth")
        self.assertEqual(item.user, self.user)

    def test_reuses_existing_ingredient_ignoring_case(self):
        existing = Ingredient.objects.create(name="Gin")
        form = BarStockForm({"ingredient_name": "gIN", "quantity": "1", "unit": "bottles"}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().ingredient, existing)
        self.assertEqual(Ingredient.objects.count(), 1)

    def test_rejects_duplicate_for_same_user(self):
        BarStock.objects.create(user=self.user, ingredient=Ingredient.objects.create(name="Gin"), quantity=1)
        form = BarStockForm({"ingredient_name": "gin", "quantity": "2", "unit": "bottles"}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("ingredient_name", form.errors)

    def test_rejects_negative_quantity(self):
        form = BarStockForm({"ingredient_name": "Gin", "quantity": "-1", "unit": "bottles"}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_blank_name_rejected(self):
        form = BarStockForm({"ingredient_name": "   ", "quantity": "1", "unit": "bottles"}, user=self.user)
        self.assertFalse(form.is_valid())


class ViewTests(TestCase):
    """Tests for the list, add, edit and delete views."""

    def setUp(self):
        self.user = make_user()
        self.other = make_user("other@example.com")
        self.gin = Ingredient.objects.create(name="Gin")
        self.mine = BarStock.objects.create(user=self.user, ingredient=self.gin, quantity=2)
        self.theirs = BarStock.objects.create(
            user=self.other, ingredient=Ingredient.objects.create(name="Mezcal"), quantity=1
        )

    def test_pages_require_login(self):
        for name, args in [("bar:list", []), ("bar:add", []), ("bar:edit", [self.mine.pk]), ("bar:delete", [self.mine.pk])]:
            url = reverse(name, args=args)
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}")

    def test_list_shows_only_own_stock(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("bar:list"))
        self.assertContains(response, "Gin")
        self.assertNotContains(response, "Mezcal")

    def test_empty_state(self):
        self.client.force_login(make_user("empty@example.com"))
        self.assertContains(self.client.get(reverse("bar:list")), "Your bar is empty")

    def test_add_creates_stock_for_current_user(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("bar:add"), {"ingredient_name": "Campari", "quantity": "1", "unit": "bottles"})
        self.assertRedirects(response, reverse("bar:list"))
        self.assertTrue(BarStock.objects.filter(user=self.user, ingredient__name="Campari").exists())

    def test_edit_updates_quantity(self):
        self.client.force_login(self.user)
        url = reverse("bar:edit", args=[self.mine.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"ingredient_name": "Gin", "quantity": "5", "unit": "bottles"})
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.quantity, Decimal("5"))

    def test_cannot_edit_or_delete_another_users_stock(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("bar:edit", args=[self.theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("bar:delete", args=[self.theirs.pk])).status_code, 404)
        self.assertTrue(BarStock.objects.filter(pk=self.theirs.pk).exists())

    def test_delete_removes_stock(self):
        self.client.force_login(self.user)
        url = reverse("bar:delete", args=[self.mine.pk])
        self.assertContains(self.client.get(url), "Remove from your bar?")
        self.assertRedirects(self.client.post(url), reverse("bar:list"))
        self.assertFalse(BarStock.objects.filter(pk=self.mine.pk).exists())

    def test_dashboard_shows_stock_count(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("core:dashboard")), "1 item in stock")
