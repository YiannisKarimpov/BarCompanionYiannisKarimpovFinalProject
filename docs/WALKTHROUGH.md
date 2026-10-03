# Bar Companion: code walkthrough and demo script

A guide to how the project fits together, with the reasons behind the main decisions.

## 1. The idea in one minute

Bar Companion helps a bartender answer "what can I make with what I have?" and run a small cocktail menu. Recipes come from the external TheCocktailDB API. Everything personal (stock, favourites, menus, roles) lives in our own PostgreSQL database.

## 2. How a request flows

Browser -> Render/gunicorn -> `config/urls.py` picks an app -> the app's `urls.py` picks a view -> the view reads the database and/or calls `recipes/services.py` -> a template renders HTML.

## 3. Apps and files

### config/
- `settings.py`: configuration. Secrets and the database URL come from environment variables (python-decouple). `AUTH_USER_MODEL` points to our custom user. Uses a database cache table. WhiteNoise serves static files.
- `urls.py`: top-level routes: `/admin/`, `/accounts/`, `/bar/`, `/recipes/`, `/menus/`, and the core pages.

### accounts/
- `models.py`: custom `User` that logs in with email and has a `role` (bartender or admin). `has_admin_access` is true for the admin role or a superuser.
- `forms.py`: registration and email login forms.
- `views.py`, `urls.py`: register, login, logout.
- `admin.py`: the Django admin screen for users.

### core/
- `views.py`: public landing page and the logged-in dashboard (stock, favourites, menus, matcher shortcuts).
- `manage_views.py`: admin-only pages: user table, role change, deactivate/reactivate, unused-ingredient cleanup. The `admin_required` decorator sends anonymous users to login and gives non-admins a 403. Admins cannot demote or deactivate themselves.

### bar/ (My bar)
- `models.py`: `Ingredient` (shared names, unique ignoring case) and `BarStock` (one line per user and ingredient, with quantity and unit).
- `forms.py`: the user types an ingredient name; the form reuses an existing ingredient or creates one, and blocks duplicates.
- `views.py`: class-based list/add/edit/delete views. `OwnStockMixin` limits every query to the logged-in user, so nobody can see or edit another bar.

### recipes/
- `services.py`: the only file that talks to TheCocktailDB. It handles retries with a short wait, caching, and turns the API's numbered ingredient fields into a clean list. Errors become one `CocktailAPIError` the views can show politely.
- `matching.py`: the "Can I make it?" engine. The free API key cannot search by ingredient, so it builds its own catalogue (by-letter lists topped up with category and glass lists), caches it for a week, and compares whole words ("rum" matches "Light rum", not "Ginger ale"). Ice and water are assumed on hand.
- `management/commands/warm_catalogue.py`: pre-loads the catalogue during deploy so users do not wait a minute.
- `models.py`: `Favourite` (drink id, name, thumbnail, unique per user and drink).
- `views.py`: browse/search, recipe detail (with "in your bar" badges, Save and Add to menu), matcher, favourites list and toggle.

### menus/
- `models.py`: `Menu` (owned by a user) and `MenuItem` (drink, cost, price). `margin` and `margin_percent` are computed properties; the menu has an average that ignores unpriced drinks.
- `forms.py`, `views.py`, `urls.py`: create/delete menus, add a drink from a recipe page, set prices, remove. Every query is filtered by owner, so another user's menu returns 404.

### templates/ and static/
- `templates/base.html`: layout, navbar (the Admin link shows only for admins) and flash messages. Each app has its own template folder extending it.
- `static/css/site.css`: the dark and gold theme on top of Bootstrap 5.

### Deployment files
- `build.sh`: install, collect static files, create the cache table, migrate, pre-load the catalogue.
- `gunicorn.conf.py`, `Procfile`: start command and a 120 second timeout.
- `requirements.txt`, `.env.example`, `.gitignore`: dependencies, example settings, and `.env` kept out of git.

## 4. Decisions worth explaining

1. **Custom user model from day one**, because changing it after migrations exist is painful. Email login suits bartenders better than usernames.
2. **Store only ids and display fields for favourites and menu items**, not whole recipes. The API stays the source of truth and pages load without API calls.
3. **Own matching engine**, because the free API cannot filter by several ingredients. Trade-off: first build of the catalogue is slow, so it is cached and pre-warmed.
4. **Ownership enforced in the queryset**, not by hiding links. A wrong user gets 404 even if they guess a URL.
5. **POST for anything that changes data**, with CSRF tokens. `require_POST` returns 405 for GET.
6. **Mocked API in tests**, so the tests are fast, repeatable and offline.

## 5. Demo script (about 5 minutes)

1. Landing page, then register a new account.
2. My bar: add Gin, Tonic water, Lime juice. Show the duplicate being rejected.
3. Can I make it?: show the ready and "one ingredient short" lists.
4. Open a cocktail: show the "In your bar" badges, press Save, and add it to a new menu.
5. Menus: set a cost and price, show margin and average margin.
6. Favourites page and dashboard cards.
7. Log in as admin: Admin link, user table, change a role, deactivate a test user.
8. Mention the tests (about 135), 97% coverage, feature branches and pull requests on GitHub, and the Render deployment.

## 6. Questions you may be asked

- **Why Django and PostgreSQL?** The course stack. Django gives auth, ORM, forms and admin; PostgreSQL is what Render offers and handles the constraints used here.
- **How is user data protected?** Hashed passwords, CSRF on every form, login required on private pages, owner-filtered queries, secrets in environment variables, HTTPS redirect when `DEBUG` is off.
- **What happens if the API is down?** `CocktailAPIError` is caught and a friendly message is shown. Cached results keep working.
- **What would you add next?** Shopping list from "almost" matches, ingredient aliases (for example "triple sec" and "Cointreau"), recipe notes, and a paid API key for production.
- **What is not finished or known limits?** The free API key is for development, so a production key is needed for a public release. Ingredient matching is word-based and the bartender is the final judge.
