"""Models for a bartender's stock.

``Ingredient`` is a shared reference list (names are unique regardless of
capitalisation) and ``BarStock`` records how much of an ingredient one user
currently holds.
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class Ingredient(models.Model):
    """A cocktail ingredient such as "Gin" or "Fresh lime juice"."""

    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        constraints = [
            # "gin" and "Gin" are the same ingredient.
            models.UniqueConstraint(Lower("name"), name="unique_ingredient_name_ci"),
        ]

    def __str__(self):
        return self.name


class BarStock(models.Model):
    """The quantity of one ingredient held by one user."""

    class Unit(models.TextChoices):
        BOTTLES = "bottles", "Bottles"
        ML = "ml", "Millilitres"
        UNITS = "units", "Units"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stock_items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="stock_items")
    quantity = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.BOTTLES)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ingredient__name"]
        verbose_name_plural = "bar stock"
        constraints = [
            # A user holds at most one stock line per ingredient.
            models.UniqueConstraint(fields=["user", "ingredient"], name="unique_stock_per_user_ingredient"),
        ]

    def __str__(self):
        return f"{self.ingredient.name}: {self.quantity} {self.unit}"
