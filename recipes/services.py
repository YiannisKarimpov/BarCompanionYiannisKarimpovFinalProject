"""Client for TheCocktailDB API.

All network access to the external API lives in this module so the rest of the
app (and the tests) can work with plain Python dictionaries. Responses are
cached briefly to stay well inside the API's fair-use limits.
"""
import hashlib
import json
import time

import requests
from django.conf import settings
from django.core.cache import cache

REQUEST_TIMEOUT_SECONDS = 8
MAX_ATTEMPTS = 3  # tries per request when the API says it is busy
RETRY_STATUSES = {429, 500, 502, 503, 504}
CACHE_SECONDS = 60 * 60
CATALOGUE_CACHE_SECONDS = 60 * 60 * 24 * 7  # the full cocktail list barely changes
MAX_INGREDIENTS = 15  # the API exposes strIngredient1 .. strIngredient15


class CocktailAPIError(Exception):
    """Raised when TheCocktailDB cannot be reached or returns unusable data."""


def _get(endpoint, params, cache_seconds=CACHE_SECONDS):
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
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            # The API answers some "nothing found" lookups with an empty body.
            data = response.json() if response.text.strip() else {}
            break
        except (requests.RequestException, ValueError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                time.sleep(0.5 * attempt)  # busy: wait a little longer each time
                continue
            raise CocktailAPIError("The cocktail service is not responding right now.") from exc

    cache.set(cache_key, data, cache_seconds)
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


def cocktails_starting_with(letter):
    """Return every cocktail whose name starts with ``letter`` (full recipes).

    The free API key cannot filter by ingredient (it returns one sample drink),
    but listing by first letter returns complete recipes, so the matcher builds
    its catalogue from these lists. Cached for a day.
    """
    letter = (letter or "").strip()[:1]
    if not letter:
        return []
    data = _get("search.php", {"f": letter}, cache_seconds=CATALOGUE_CACHE_SECONDS)
    return [parse_drink(raw) for raw in (data.get("drinks") or [])]


def list_values(kind):
    """Return the API's category names (``kind="c"``) or glass names (``"g"``)."""
    key = {"c": "strCategory", "g": "strGlass"}[kind]
    data = _get("list.php", {kind: "list"}, cache_seconds=CATALOGUE_CACHE_SECONDS)
    return [row[key] for row in (data.get("drinks") or []) if row.get(key)]


def _filter_list(kind, value):
    """Return the raw drinks of one category (``kind="c"``) or glass (``"g"``).

    The free key caps each list at 100 drinks, each with only an id, name and
    picture. The API sends the text "None Found" for no match, which becomes [].
    """
    data = _get("filter.php", {kind: value.replace(" ", "_")}, cache_seconds=CATALOGUE_CACHE_SECONDS)
    drinks = data.get("drinks")
    return drinks if isinstance(drinks, list) else []


def drink_ids_by(kind, value):
    """Return the ids of cocktails in one category or served in one glass.

    Different categories and glasses overlap only partly, so together they
    reach drinks the by-letter lists miss.
    """
    return [int(raw["idDrink"]) for raw in _filter_list(kind, value)]


def drinks_by_category(category):
    """Return the cocktails in one category as small cards (id, name, picture).

    Shares its cached API response with the matcher's catalogue builder.
    """
    return [
        {"id": int(raw["idDrink"]), "name": raw.get("strDrink") or "Unnamed cocktail", "thumb": raw.get("strDrinkThumb") or "", "category": category}
        for raw in _filter_list("c", category)
    ]


def get_cocktail(drink_id, cache_seconds=CACHE_SECONDS):
    """Return one cocktail by its API id, or None if it does not exist."""
    data = _get("lookup.php", {"i": drink_id}, cache_seconds=cache_seconds)
    drinks = data.get("drinks") or []
    return parse_drink(drinks[0]) if drinks else None
