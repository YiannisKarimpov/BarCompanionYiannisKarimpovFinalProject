"""URL routes for the menu builder."""
from django.urls import path

from . import views

app_name = "menus"

urlpatterns = [
    path("", views.MenuListView.as_view(), name="list"),
    path("new/", views.MenuCreateView.as_view(), name="create"),
    path("<int:pk>/", views.MenuDetailView.as_view(), name="detail"),
    path("<int:pk>/delete/", views.MenuDeleteView.as_view(), name="delete"),
    path("add/<int:drink_id>/", views.add_item, name="add_item"),
    path("items/<int:pk>/edit/", views.ItemUpdateView.as_view(), name="edit_item"),
    path("items/<int:pk>/remove/", views.remove_item, name="remove_item"),
]
