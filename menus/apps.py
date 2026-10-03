"""App configuration for menus."""
from django.apps import AppConfig


class MenusConfig(AppConfig):
    """Registers the menu builder app."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "menus"
