"""Django admin screens for menus and their items."""
from django.contrib import admin

from .models import Menu, MenuItem


class MenuItemInline(admin.TabularInline):
    """Edit a menu's items on the menu page."""
    model = MenuItem
    extra = 0


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    """Admin screen for menus."""
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__email")
    inlines = [MenuItemInline]
