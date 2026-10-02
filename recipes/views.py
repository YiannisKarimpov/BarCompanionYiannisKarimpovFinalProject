"""Views for browsing cocktail recipes from TheCocktailDB (public pages)."""
from django.http import Http404
from django.shortcuts import render

from bar.models import BarStock

from . import services

SUGGESTED_SEARCHES = ["Margarita", "Mojito", "Negroni", "Old Fashioned", "Daiquiri", "Martini"]


def browse(request):
    """Search recipes by name. With no search term, show suggestions instead."""
    query = request.GET.get("q", "").strip()
    results, error = [], None
    if query:
        try:
            results = services.search_cocktails(query)
        except services.CocktailAPIError as exc:
            error = str(exc)
    context = {"query": query, "results": results, "error": error, "suggestions": SUGGESTED_SEARCHES}
    return render(request, "recipes/browse.html", context)


def detail(request, drink_id):
    """Show one recipe. Logged-in users see which ingredients are in their bar."""
    try:
        drink = services.get_cocktail(drink_id)
    except services.CocktailAPIError as exc:
        return render(request, "recipes/detail.html", {"error": str(exc)}, status=503)
    if drink is None:
        raise Http404("Cocktail not found")

    if request.user.is_authenticated:
        in_stock = {
            name.lower()
            for name in BarStock.objects.filter(user=request.user).values_list("ingredient__name", flat=True)
        }
        for ingredient in drink["ingredients"]:
            ingredient["in_stock"] = ingredient["name"].lower() in in_stock
    return render(request, "recipes/detail.html", {"drink": drink})
