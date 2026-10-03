"""Models for the menu builder.

A ``Menu`` belongs to one user and holds ``MenuItem`` lines. Each line points to
a TheCocktailDB recipe by id (name and picture are copied so the menu page needs
no API calls) and carries the bar's own cost and selling price.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

HUNDRED = Decimal("100")


class Menu(models.Model):
    """A named list of drinks with costs and prices, owned by one user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="menus")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_menu_name_per_user"),
        ]

    def __str__(self):
        return self.name

    def average_margin_percent(self):
        """Average margin % across the priced items, or None if none are priced."""
        margins = [item.margin_percent for item in self.items.all() if item.margin_percent is not None]
        if not margins:
            return None
        return (sum(margins) / len(margins)).quantize(Decimal("0.1"))


class MenuItem(models.Model):
    """One drink on a menu, with what it costs to make and what it sells for."""

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    drink_id = models.PositiveIntegerField()
    name = models.CharField(max_length=200)
    thumb = models.URLField(max_length=500, blank=True)
    cost = models.DecimalField(
        "Cost per drink (€)", max_digits=7, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(0)]
    )
    price = models.DecimalField(
        "Selling price (€)", max_digits=7, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["menu", "drink_id"], name="unique_drink_per_menu"),
        ]

    def __str__(self):
        return f"{self.name} on {self.menu}"

    @property
    def margin(self):
        """Profit per drink: price minus cost."""
        return self.price - self.cost

    @property
    def margin_percent(self):
        """Margin as a percentage of the price, or None when no price is set."""
        if self.price <= 0:
            return None
        return (self.margin / self.price * HUNDRED).quantize(Decimal("0.1"))
