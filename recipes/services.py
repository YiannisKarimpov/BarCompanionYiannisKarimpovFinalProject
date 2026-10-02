"""Client for TheCocktailDB API.

All network access to the external API lives in this module so the rest of the
app (and the tests) can work with plain Python dictionaries. Responses are
cached briefly to stay well inside the API's fair-use limits.
"""
import hashlib
import json

import requests
from django.conf import settings
from django.core.cache import cache

REQUEST_TIMEOUT_SECONDS = 8
CACHE_SECONDS = 60 * 60
MAX_INGREDIENTS = 15  # the API exposes strIngredient1 .. strIngredient15


class CocktailAPIError(Exception):
    """Raised when TheCocktailDB cannot be reached or returns unusable data."""


def _get(endpoint, params):
    """Call one API endpoint and return the decoded JSON, using the cache.

    Raises CocktailAPIError on any network, HTTP or JSON problem.
    """
    cache_key = "cocktaildb:" + hashlib.sha256(
        json.dumps([endpoint, sorted(params.items())]).encode()
    ).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"{settings.COCKTAILDB_BASE_URL.rstrip('/')}/{settings.COCKTAILDB_API_KEY}/{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CocktailAPIError("The cocktail service is not responding right now.") from exc

    cache.set(cache_key, data, CACHE_SECONDS)
    return data


def parse_drink(raw):
    """Turn one raw API drink into a small, predictable dictionary.

    The API stores ingredients as numbered fields (strIngredient1..15 with
    matching strMeasure1..15), most of them null. They are collected here into
    a list of {"name", "measure"} pairs in order.
    """
    ingredients = []
    for number in range(1, MAX_INGREDIENTS + 1):
        name = (raw.get(f"strIngredient{number}") or "").strip()
        if not name:
            continue
        ingredients.append({"name": name, "measure": (raw.get(f"strMeasure{number}") or "").strip()})
    return {
        "id": int(raw["idDrink"]),
        "name": raw.get("strDrink") or "Unnamed cocktail",
        "category": raw.get("strCategory") or "",
        "alcoholic": raw.get("strAlcoholic") or "",
        "glass": raw.get("strGlass") or "",
        "instructions": raw.get("strInstructions") or "",
        "thumb": raw.get("strDrinkThumb") or "",
        "ingredients": ingredients,
    }


def search_cocktails(query):
    """Return cocktails whose name matches ``query`` (an empty list if none)."""
    query = (query or "").strip()
    if not query:
        return []
    data = _get("search.php", {"s": query})
    return [parse_drink(raw) for raw in (data.get("drinks") or [])]


def get_cocktail(drink_id):
    """Return one cocktail by its API id, or None if it does not exist."""
    data = _get("lookup.php", {"i": drink_id})
    drinks = data.get("drinks") or []
    return parse_drink(drinks[0]) if drinks else None
