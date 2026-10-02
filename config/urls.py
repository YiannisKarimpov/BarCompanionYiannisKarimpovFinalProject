"""Root URL configuration for Bar Companion."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("bar/", include("bar.urls")),
    path("recipes/", include("recipes.urls")),
    path("", include("core.urls")),
]
