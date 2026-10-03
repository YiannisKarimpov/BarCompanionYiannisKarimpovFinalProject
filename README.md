# Bar Companion

A cocktail and bar-management web app for bartenders, built with Django and PostgreSQL as the final project for the UCD Dublin Professional Academy Full Stack Software Development course.

Users can register and log in, browse cocktail recipes from an external API, track their bar's stock, see which cocktails they can make, save favourites, and build costed menus. Admins get a small management area for users and ingredients.

Live site: https://bar-companion-z2oo.onrender.com (the free Render plan sleeps when idle, so the first load can take a while).

## Status

Feature complete: accounts and roles, My bar stock, recipe browsing, "Can I make it?" matcher, favourites, menu builder and site admin. Remaining work is polish only. See `docs/WALKTHROUGH.md` for a file-by-file tour of the code.

## How "Can I make it?" works

The free TheCocktailDB key cannot search by ingredient (it returns a single sample drink), so `recipes/matching.py` builds its own catalogue and compares each recipe with your bar locally. The catalogue combines the by-letter lists (complete recipes, but each list is capped) with the drinks found by listing every category and glass, looking up any recipe not yet known. Ingredient names are matched by whole words ("rum" matches "Light rum", "gin" does not match "Ginger ale"). Cocktails with nothing missing are listed as makeable now, then those one and two ingredients short with what is missing. Ice and water are assumed to be on hand. Building the catalogue takes about a minute, so it is cached in the database for a week and pre-loaded by `python manage.py warm_catalogue` (run automatically by `build.sh` on deploy). If requests fail while it loads, the page warns that the list may be incomplete and a refresh fills the gaps.

## Favourites

Logged-in users can press Save on any recipe to add it to their favourites (press again to remove it). A favourite stores only the TheCocktailDB drink id, name and picture (`recipes.models.Favourite`, unique per user and drink), so the Favourites page and the dashboard card load without calling the API. Saving is a POST request protected by CSRF and requires login.

## Menu builder

Bartenders can create named menus (`/menus/`), add any recipe to one with "Add to menu" on the recipe page, then set each drink's cost and selling price. The menu page shows the margin in euros and as a percentage of the price for every drink, plus the menu's average margin (drinks without a price are left out of the average and flagged). A menu item stores the TheCocktailDB drink id with its name and picture, so menu pages need no API calls. Menus are private: every view filters by the logged-in user, so another user's menu returns 404.

## Site admin

Users with the admin role (and superusers) get an Admin link in the navbar leading to `/manage/`: site totals, a user table showing each person's stock, menus and favourites, role changes, and deactivate/reactivate for accounts (a deactivated user cannot log in). Admins cannot change their own role or deactivate themselves, so the site can never be left without an admin. A second page lists the shared ingredient names and deletes unused ones. Anonymous visitors are sent to log in; logged-in bartenders get a 403 page. Django's own `/admin/` stays available for low-level data editing.

## Bonus features

Beyond the required register/login, dashboard and API integration:

- Recipe search by name, with suggested searches
- "Can I make it?" matcher: cocktails ready now, or one or two ingredients short
- Favourites (save and remove recipes, shown on the dashboard)
- Menu builder with cost, price, margin and average margin
- Admin-only management pages for users, roles and ingredient names
- Caching and retries around the external API, with a pre-load step on deploy

## Tech stack

- Django 5.2 (Python), Django templates, Bootstrap 5
- PostgreSQL (SQLite fallback for quick local runs and tests)
- TheCocktailDB external API (recipe search and details)
- Gunicorn + WhiteNoise, deployed on Render

## Project layout

```
config/       project settings, root URLs, WSGI
accounts/     custom User model (email login, role), register/login/logout
core/         landing page, dashboard, admin-only /manage/ pages
bar/          ingredient stock (My bar)
recipes/      TheCocktailDB client, matcher, favourites
menus/        menu builder: costs, prices and margins
templates/    base.html and per-app templates
static/       site CSS
docs/         WALKTHROUGH.md: tour of the code and demo script
```

## Run locally

1. Create and activate a virtual environment, then install dependencies:

   ```
   python -m venv venv
   venv\Scripts\activate          (Windows)   or   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and edit it. To use PostgreSQL, create a database called `barcompanion` and set `DATABASE_URL`. If `DATABASE_URL` is removed, the app uses SQLite.

3. Create the cache table, apply migrations, pre-load the cocktail catalogue (about a minute, once a week), create an admin user, and start the server:

   ```
   python manage.py createcachetable
   python manage.py migrate
   python manage.py warm_catalogue
   python manage.py createsuperuser
   python manage.py runserver
   ```

4. Open http://127.0.0.1:8000/

## Run the tests

```
python manage.py test
```

Tests are written with Python's built-in `unittest` framework through Django's `TestCase` classes and test runner (`python manage.py test`), using a temporary database. There are about 135 of them. No test touches the network: calls to TheCocktailDB are replaced with mocks. Covered areas: the API client (parsing, caching, retries, errors), ingredient matching, the catalogue builder, stock, favourites, menus and margin maths, and access control on every private page (anonymous, bartender and admin users). Line coverage measured with `coverage` is about 97%.

## Deploy to Render

These steps deploy the app from scratch on Render's free plan. The project was developed and tested with Python 3.13; set a `PYTHON_VERSION` environment variable on the web service if you need to pin the version.

1. Push the repository to GitHub (or unzip the submitted project and push it to your own repository).
2. In Render, create a **PostgreSQL** database (Dashboard, New, PostgreSQL). Copy its **Internal Database URL** once it is available.
3. Create a **Web Service** from the repository with these settings:
   - Build command: `bash build.sh`
   - Start command: `gunicorn config.wsgi` (`gunicorn.conf.py` sets a 120 second timeout)
4. Add these environment variables to the web service:

   | Variable | Value |
   | --- | --- |
   | `SECRET_KEY` | a long random string (for example from `python -c "import secrets; print(secrets.token_urlsafe(50))"`) |
   | `DEBUG` | `False` |
   | `DATABASE_URL` | the Internal Database URL from step 2 |
   | `ALLOWED_HOSTS` | your Render hostname, such as `your-app.onrender.com` (Render's `RENDER_EXTERNAL_HOSTNAME` is also added automatically) |
   | `COCKTAILDB_API_KEY` | optional; defaults to the free test key `1` |

5. Deploy. `build.sh` installs the requirements, collects static files, creates the cache table, runs migrations and pre-loads the cocktail catalogue (best effort: if the API is busy the site still deploys and the catalogue loads on first use).
6. Create the first admin account. The free plan has no Render shell, so run `python manage.py createsuperuser` on your own machine with `DATABASE_URL` temporarily set to the database's **External Database URL**. Alternatively, register a normal account on the site and ask an existing admin to promote it at `/manage/`.

### After deploying, check

- The home page loads over HTTPS and the Sign up and Log in pages work.
- A new account can add stock in My bar and see results on Can I make it?.
- A recipe can be saved to favourites and added to a menu.
- An admin account sees the Admin link; a bartender account does not and gets a 403 page on `/manage/`.

### Deployment notes

- The free web service sleeps when idle, so the first request after a quiet period can take up to a minute.
- Render's free PostgreSQL database expires after 30 days; recreate it or upgrade it for a longer-lived site, then redeploy so migrations run on the new database.
- TheCocktailDB's key `1` is a free development key; check the provider's terms and use a production key for a public release.

## Security

- **Authentication:** Django's built-in user system with a custom email-based user model. Passwords are hashed (PBKDF2) and checked by Django's password validators.
- **Authorization:** every private page requires login. Roles (bartender, admin) are enforced on the server: `/manage/` returns 403 to non-admins and redirects anonymous visitors to log in.
- **Data isolation:** each query for stock, favourites and menus is filtered by the logged-in user, so guessing another user's URL returns 404.
- **CSRF:** enabled for all forms; everything that changes data uses POST (`require_POST`), so links cannot trigger changes.
- **Injection and XSS:** all database access goes through the Django ORM (parameterised queries) and templates auto-escape output.
- **Redirects:** the `next` parameter on favourites is checked with Django's `url_has_allowed_host_and_scheme`.
- **Safeguards:** admins cannot demote or deactivate themselves; deactivated users cannot log in.
- **Secrets:** the secret key and database credentials come from environment variables. `.env` is git-ignored and only `.env.example` is committed.
- **HTTPS:** with `DEBUG=False` the app redirects to HTTPS, uses secure session and CSRF cookies and sends an HSTS header.
- **Tested:** access control, ownership and self-protection rules each have automated tests.

## Front end

Templates extend one `base.html` (Bootstrap 5 layout, navbar that collapses on tablets and phones, flash messages). Pages use Bootstrap's responsive grid and tables scroll horizontally on small screens. Every form field has a label, recipe images have alt text, and the colour scheme keeps text readable on the dark background.
