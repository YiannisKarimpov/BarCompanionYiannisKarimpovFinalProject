"""Views for browsing cocktail recipes from TheCocktailDB, matching them to stock and saving favourites."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from bar.models import BarStock

from . import matching, services
from .models import Favourite

DEFAULT_LETTER = "a"
SUGGESTED_SEARCHES = ["Margarita", "Mojito", "Negroni", "Old Fashioned", "Daiquiri", "Martini"]


def browse(request):
    """Browse recipes: search by name, filter by category, or page through A-Z.

    With nothing chosen, the page lists the cocktails starting with "a" so it is
    never empty. Each choice costs one API request, cached for a week and shared
    with the "Can I make it?" catalogue.
    """
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    letter = request.GET.get("letter", "").strip().lower()[:1]
    if not letter or letter not in matching.CATALOGUE_LETTERS:
        letter = DEFAULT_LETTER

    results, error, heading = [], None, ""
    try:
        categories = services.list_values("c")
    except services.CocktailAPIError:
        categories = []  # the filter just disappears; the rest of the page still works
    category = category[:40]  # any name is safe: the API just answers "none" for unknown ones

    try:
        if query:
            results = services.search_cocktails(query)
        elif category:
            results = sorted(services.drinks_by_category(category), key=lambda drink: drink["name"].lower())
            heading = f"{category}: {len(results)} cocktail{'s' if len(results) != 1 else ''}"
        else:
            results = sorted(services.cocktails_starting_with(letter), key=lambda drink: drink["name"].lower())
            heading = f"Cocktails starting with {letter.upper()}"
    except services.CocktailAPIError as exc:
        error = str(exc)

    context = {
        "query": query,
        "results": results,
        "error": error,
        "heading": heading,
        "suggestions": SUGGESTED_SEARCHES,
        "categories": categories,
        "active_category": category,
        "active_letter": "" if (query or category) else letter,
        "letters": list(matching.CATALOGUE_LETTERS),
    }
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
