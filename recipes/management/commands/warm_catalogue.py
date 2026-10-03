"""Load the cocktail catalogue into the cache ahead of time.

Building the catalogue takes about a minute on a cold cache, which is too long
for a web request. Run this after deploying (the Render build script does) so
the first visitor to "Can I make it?" gets an instant page.
"""
from django.core.management.base import BaseCommand

from recipes import matching, services


class Command(BaseCommand):
    help = "Fetch every cocktail from TheCocktailDB and cache the catalogue."

    def handle(self, *args, **options):
        try:
            drinks, failures = matching.load_catalogue()
        except services.CocktailAPIError as exc:
            self.stderr.write(f"Could not reach the cocktail service: {exc}")
            return
        message = f"Cached {len(drinks)} cocktails."
        if failures:
            message += f" {failures} requests failed, so run this again to fill the gaps."
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(message))
