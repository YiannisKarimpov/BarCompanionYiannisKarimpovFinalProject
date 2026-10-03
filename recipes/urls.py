"""URL routes for recipe browsing."""
from django.urls import path

from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.browse, name="browse"),
    path("can-i-make-it/", views.can_i_make_it, name="matcher"),
    path("<int:drink_id>/", views.detail, name="detail"),
]
