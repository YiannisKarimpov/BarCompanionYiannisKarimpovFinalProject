"""App configuration for bar."""
from django.apps import AppConfig


class BarConfig(AppConfig):
    """Registers the bar (stock) app."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "bar"
