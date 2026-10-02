"""Admin registration for ingredients and stock."""
from django.contrib import admin

from .models import BarStock, Ingredient


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Manage the shared ingredient list."""

    search_fields = ("name",)


@admin.register(BarStock)
class BarStockAdmin(admin.ModelAdmin):
    """Inspect stock lines across all users."""

    list_display = ("user", "ingredient", "quantity", "unit", "updated_at")
    list_filter = ("unit",)
    search_fields = ("user__email", "ingredient__name")
