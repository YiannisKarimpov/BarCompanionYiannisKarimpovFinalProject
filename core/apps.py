"""App configuration for core."""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Registers the core app."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
