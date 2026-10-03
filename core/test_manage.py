"""Tests for the site admin pages (/manage/)."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from bar.models import BarStock, Ingredient
from menus.models import Menu
from recipes.models import Favourite


def make_user(email, role=User.Role.BARTENDER, **extra):
    return User.objects.create_user(email=email, password="a-Strong-pass-2026", first_name="T", role=role, **extra)


class AccessTests(TestCase):
    def setUp(self):
        self.bartender = make_user("bar@example.com")
        self.admin = make_user("admin@example.com", User.Role.ADMIN)
        self.target = make_user("target@example.com")
        self.ingredient = Ingredient.objects.create(name="Gin")
        self.urls = [
            ("get", reverse("core:manage")),
            ("get", reverse("core:manage_ingredients")),
            ("post", reverse("core:manage_role", args=[self.target.pk])),
            ("post", reverse("core:manage_active", args=[self.target.pk])),
            ("post", reverse("core:manage_ingredient_delete", args=[self.ingredient.pk])),
        ]

    def test_anonymous_is_sent_to_login(self):
        for method, url in self.urls:
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("/login/", response["Location"])

    def test_bartender_gets_403_and_changes_nothing(self):
        self.client.force_login(self.bartender)
        for method, url in self.urls:
            self.assertEqual(getattr(self.client, method)(url, {"role": "admin"}).status_code, 403, url)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.BARTENDER)
        self.assertTrue(self.target.is_active)
        self.assertTrue(Ingredient.objects.exists())

    def test_admin_role_has_access(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("core:manage")).status_code, 200)

    def test_superuser_has_access_even_with_bartender_role(self):
        boss = User.objects.create_superuser(email="boss@example.com", password="a-Strong-pass-2026", first_name="B")
        User.objects.filter(pk=boss.pk).update(role=User.Role.BARTENDER)
        boss.refresh_from_db()
        self.client.force_login(boss)
        self.assertEqual(self.client.get(reverse("core:manage")).status_code, 200)

    def test_navbar_link_only_for_admins(self):
        manage = reverse("core:manage")
        self.client.force_login(self.bartender)
        self.assertNotContains(self.client.get(reverse("core:dashboard")), f'href="{manage}"')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("core:dashboard")), f'href="{manage}"')


class UserManagementTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", User.Role.ADMIN)
        self.target = make_user("target@example.com")
        self.client.force_login(self.admin)

    def test_overview_lists_users_with_activity(self):
        ingredient = Ingredient.objects.create(name="Gin")
        BarStock.objects.create(user=self.target, ingredient=ingredient, quantity=1)
        Menu.objects.create(user=self.target, name="M")
        Favourite.objects.create(user=self.target, drink_id=1, name="X")
        response = self.client.get(reverse("core:manage"))
        self.assertContains(response, "target@example.com")
        row = next(u for u in response.context["users"] if u == self.target)
        self.assertEqual((row.stock_total, row.menu_total, row.favourite_total), (1, 1, 1))
        self.assertEqual(response.context["totals"]["users"], 2)

    def test_change_role(self):
        self.client.post(reverse("core:manage_role", args=[self.target.pk]), {"role": "admin"})
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.ADMIN)

    def test_invalid_role_rejected(self):
        self.client.post(reverse("core:manage_role", args=[self.target.pk]), {"role": "owner"})
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.BARTENDER)

    def test_cannot_change_own_role_or_deactivate_self(self):
        self.client.post(reverse("core:manage_role", args=[self.admin.pk]), {"role": "bartender"})
        self.client.post(reverse("core:manage_active", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)
        self.assertTrue(self.admin.is_active)

    def test_deactivate_and_reactivate_blocks_login(self):
        url = reverse("core:manage_active", args=[self.target.pk])
        self.client.post(url)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertFalse(self.client.__class__().login(email="target@example.com", password="a-Strong-pass-2026"))
        self.client.post(url)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_unknown_user_404(self):
        self.assertEqual(self.client.post(reverse("core:manage_active", args=[9999])).status_code, 404)

    def test_get_not_allowed_on_actions(self):
        self.assertEqual(self.client.get(reverse("core:manage_role", args=[self.target.pk])).status_code, 405)


class IngredientManagementTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", User.Role.ADMIN)
        self.client.force_login(self.admin)

    def test_unused_ingredient_can_be_deleted(self):
        ingredient = Ingredient.objects.create(name="Ginn")
        self.client.post(reverse("core:manage_ingredient_delete", args=[ingredient.pk]))
        self.assertFalse(Ingredient.objects.exists())

    def test_ingredient_in_use_is_kept(self):
        ingredient = Ingredient.objects.create(name="Gin")
        BarStock.objects.create(user=make_user("b@example.com"), ingredient=ingredient, quantity=1)
        response = self.client.post(reverse("core:manage_ingredient_delete", args=[ingredient.pk]), follow=True)
        self.assertTrue(Ingredient.objects.exists())
        self.assertContains(response, "in use")

    def test_list_shows_usage(self):
        ingredient = Ingredient.objects.create(name="Gin")
        BarStock.objects.create(user=make_user("b@example.com"), ingredient=ingredient, quantity=1)
        response = self.client.get(reverse("core:manage_ingredients"))
        self.assertContains(response, "Gin")
        self.assertEqual(response.context["ingredients"][0].in_bars, 1)
