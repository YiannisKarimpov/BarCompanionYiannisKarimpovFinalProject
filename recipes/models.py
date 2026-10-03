"""Models for saved recipes.

Recipes themselves live in TheCocktailDB, so a favourite stores only the
API's drink id plus the name and picture needed to list it without another
API call.
"""
from django.conf import settings
from django.db import models


class Favourite(models.Model):
    """One cocktail saved by one user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favourites")
    drink_id = models.PositiveIntegerField()
    name = models.CharField(max_length=200)
    thumb = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # A cocktail can be saved only once per user.
            models.UniqueConstraint(fields=["user", "drink_id"], name="unique_favourite_per_user_drink"),
        ]

    def __str__(self):
        return f"{self.name} (saved by {self.user})"
