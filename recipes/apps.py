"""App configuration for recipes."""
from django.apps import AppConfig


class RecipesConfig(AppConfig):
    """Registers the recipes app."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "recipes"
