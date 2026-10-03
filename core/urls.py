"""URL routes for the core app."""
from django.urls import path

from . import manage_views, views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("manage/", manage_views.overview, name="manage"),
    path("manage/users/<int:pk>/role/", manage_views.change_role, name="manage_role"),
    path("manage/users/<int:pk>/active/", manage_views.toggle_active, name="manage_active"),
    path("manage/ingredients/", manage_views.ingredients, name="manage_ingredients"),
    path("manage/ingredients/<int:pk>/delete/", manage_views.delete_ingredient, name="manage_ingredient_delete"),
]
