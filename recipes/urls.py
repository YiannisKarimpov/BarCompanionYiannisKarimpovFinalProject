"""URL routes for recipe browsing."""
from django.urls import path

from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.browse, name="browse"),
    path("<int:drink_id>/", views.detail, name="detail"),
]
