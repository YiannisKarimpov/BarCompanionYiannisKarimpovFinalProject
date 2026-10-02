"""URL routes for the My bar pages."""
from django.urls import path

from . import views

app_name = "bar"

urlpatterns = [
    path("", views.StockListView.as_view(), name="list"),
    path("add/", views.StockCreateView.as_view(), name="add"),
    path("<int:pk>/edit/", views.StockUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.StockDeleteView.as_view(), name="delete"),
]
