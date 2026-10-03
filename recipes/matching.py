"""Work out which cocktails a bartender can make from the bar's current stock.

The free TheCocktailDB key cannot search by ingredient (it returns a single
sample drink), so the matcher builds its own catalogue and compares each recipe
with the stock locally. The catalogue is the by-letter lists (complete recipes,
but each list is capped), topped up with the drinks found by listing every
category and every glass (ids only, capped too) and looking up any recipe not
already known. Everything is cached for a day, so only the first visit after a
restart is slow.

Everything that touches the network goes through ``recipes.services`` so tests
can replace it, and the API responses are cached there.
"""
import re
import string
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache

from . import services

CATALOGUE_LETTERS = string.ascii_lowercase + string.digits
MAX_WORKERS = 5  # parallel API requests (kept low to stay inside the API's fair use)
MAX_CLOSE = 12   # cap on the "two ingredients away" list
CATALOGUE_CACHE_KEY = "recipes:catalogue:v1"
STAPLES = {"ice", "ice cubes", "ice cube", "crushed ice", "cracked ice", "water"}


def _tokens(name):
    """Lower-case words of ``name`` with a simple plural ("limes") removed."""
    words = re.findall(r"[a-z0-9]+", (name or "").lower())
    return {word[:-1] if len(word) > 3 and word.endswith("s") else word for word in words}


def is_staple(name):
    """True for ingredients assumed to be on hand in any bar, such as ice."""
    return " ".join(re.findall(r"[a-z0-9]+", (name or "").lower())) in STAPLES


def names_match(stock_name, recipe_name):
    """True when a stock item can stand in for a recipe ingredient.

    Matching is by whole words, in either direction, so "rum" matches "Light
    rum" and "Dry vermouth" matches "Vermouth", but "gin" does not match
    "Ginger ale". It is deliberately simple; the bartender is the final judge.
    """
    stock, recipe = _tokens(stock_name), _tokens(recipe_name)
    if not stock or not recipe:
        return False
    return stock <= recipe or recipe <= stock


def missing_ingredients(drink, stock_names):
    """Names of the recipe's ingredients that nothing in stock covers."""
    return [
        ingredient["name"]
        for ingredient in drink["ingredients"]
        if not is_staple(ingredient["name"])
        and not any(names_match(stock, ingredient["name"]) for stock in stock_names)
    ]


def _parallel(function, items):
    """Run ``function`` over ``items`` in a few threads, keeping the order."""
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return list(pool.map(function, items))


def _attempt(function, *args):
    """Call ``function``; return ``(result, None)`` or ``(None, error)``."""
    try:
        return function(*args), None
    except services.CocktailAPIError as exc:
        return None, exc


def load_catalogue():
    """Return ``(drinks, failures)``: every cocktail we can find, de-duplicated.

    The finished catalogue is cached for a week. A request that fails is skipped
    and counted rather than stopping everything; requests that succeeded stay
    cached, so reloading the page fills the gaps.
    ``services.CocktailAPIError`` is raised only if every by-letter request
    fails, which means the API is unreachable.
    """
    cached = cache.get(CATALOGUE_CACHE_KEY)
    if cached is not None:
        return cached, 0

    failures = 0
    letters = _parallel(lambda letter: _attempt(services.cocktails_starting_with, letter), CATALOGUE_LETTERS)
    errors = [error for _drinks, error in letters if error]
    if len(errors) == len(letters):
        raise errors[0]
    failures += len(errors)
    catalogue = {drink["id"]: drink for drinks, _error in letters if drinks for drink in drinks}

    # Top up with drinks the capped by-letter lists miss: list the categories
    # and glasses, collect their ids, then fetch any recipe not yet known.
    jobs = []
    for kind in ("c", "g"):
        names, error = _attempt(services.list_values, kind)
        if error:
            failures += 1
        else:
            jobs += [(kind, name) for name in names]
    extra_ids = set()
    for ids, error in _parallel(lambda job: _attempt(services.drink_ids_by, *job), jobs):
        if error:
            failures += 1
        else:
            extra_ids.update(ids)
    unknown = sorted(extra_ids - catalogue.keys())
    ttl = services.CATALOGUE_CACHE_SECONDS
    for drink, error in _parallel(lambda drink_id: _attempt(services.get_cocktail, drink_id, ttl), unknown):
        if error:
            failures += 1
        elif drink:
            catalogue[drink["id"]] = drink
    drinks = list(catalogue.values())
    if failures == 0:  # only keep a complete catalogue; a partial one is retried
        cache.set(CATALOGUE_CACHE_KEY, drinks, services.CATALOGUE_CACHE_SECONDS)
    return drinks, failures


def find_matches(stock_names):
    """Split cocktails by how many ingredients the bar is missing.

    Returns a dict with:

    * ``ready``  - nothing missing
    * ``almost`` - exactly one ingredient missing (``missing`` lists it)
    * ``close``  - exactly two missing (``missing`` lists both), at most
      ``MAX_CLOSE`` of them
    * ``checked`` - how many cocktails were compared
    * ``incomplete`` - True if some API requests failed, so the catalogue may be short

    A recipe only counts as "almost" or "close" if at least one of its
    ingredients is in stock. Raises ``services.CocktailAPIError`` if the API
    cannot be reached.
    """
    stock_names = [name for name in dict.fromkeys(stock_names) if name]
    catalogue, failures = load_catalogue()
    ready, almost, close = [], [], []
    for drink in catalogue:
        needed = [i for i in drink["ingredients"] if not is_staple(i["name"])]
        if not needed:
            continue
        missing = missing_ingredients(drink, stock_names)
        if not missing:
            ready.append(drink)
        elif len(missing) < len(needed):  # at least one ingredient is in stock
            if len(missing) == 1:
                almost.append({**drink, "missing": missing})
            elif len(missing) == 2:
                close.append({**drink, "missing": missing})
    for group in (ready, almost, close):
        group.sort(key=lambda drink: drink["name"].lower())
    return {"ready": ready, "almost": almost, "close": close[:MAX_CLOSE], "checked": len(catalogue), "incomplete": failures > 0}
