"""Views for browsing cocktail recipes from TheCocktailDB, matching them to stock and saving favourites."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from bar.models import BarStock

from . import matching, services
from .models import Favourite

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
        stock_names = list(
            BarStock.objects.filter(user=request.user).values_list("ingredient__name", flat=True)
        )
        for ingredient in drink["ingredients"]:
            ingredient["staple"] = matching.is_staple(ingredient["name"])
            ingredient["in_stock"] = any(matching.names_match(stock, ingredient["name"]) for stock in stock_names)
        is_favourite = Favourite.objects.filter(user=request.user, drink_id=drink["id"]).exists()
        menus = list(request.user.menus.all())
    else:
        is_favourite, menus = False, []
    return render(request, "recipes/detail.html", {"drink": drink, "is_favourite": is_favourite, "menus": menus})


@login_required
def can_i_make_it(request):
    """Show the cocktails the user can make now and those one ingredient short."""
    stock_names = list(
        BarStock.objects.filter(user=request.user)
        .order_by("-updated_at")
        .values_list("ingredient__name", flat=True)
    )
    context = {
        "has_stock": bool(stock_names),
        "stock_names": sorted(set(stock_names), key=str.lower),
        "ready": [],
        "almost": [],
        "close": [],
        "checked": 0,
        "incomplete": False,
        "error": None,
    }
    if stock_names:
        try:
            context.update(matching.find_matches(stock_names))
        except services.CocktailAPIError as exc:
            context["error"] = str(exc)
    return render(request, "recipes/matcher.html", context)


@login_required
def favourites(request):
    """List the recipes the user has saved, newest first."""
    return render(request, "recipes/favourites.html", {"favourites": Favourite.objects.filter(user=request.user)})


@login_required
@require_POST
def toggle_favourite(request, drink_id):
    """Save the recipe if it is not a favourite yet, otherwise remove it."""
    existing = Favourite.objects.filter(user=request.user, drink_id=drink_id)
    if existing.exists():
        existing.delete()
    else:
        try:
            drink = services.get_cocktail(drink_id)
        except services.CocktailAPIError:
            drink = None
        if drink is None:
            raise Http404("Cocktail not found")
        Favourite.objects.create(user=request.user, drink_id=drink["id"], name=drink["name"], thumb=drink["thumb"])
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("recipes:detail", drink_id=drink_id)
