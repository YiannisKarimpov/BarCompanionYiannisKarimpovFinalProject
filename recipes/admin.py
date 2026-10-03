"""Django admin screen for saved favourites."""
from django.contrib import admin

from .models import Favourite


@admin.register(Favourite)
class FavouriteAdmin(admin.ModelAdmin):
    """Admin screen for favourites."""
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__email")
