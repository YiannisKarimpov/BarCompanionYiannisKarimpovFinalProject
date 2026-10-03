# Bar Companion

A cocktail and bar-management web app for bartenders, built with Django and PostgreSQL as the final project for the UCD Dublin Professional Academy Full Stack Software Development course.

Users can register and log in, then (as features are added week by week) browse cocktail recipes from an external API, track their bar's stock, see which cocktails they can make, save favourites, and build costed menus.

## Status

Week 2 skeleton, My bar stock management, recipe browsing from TheCocktailDB, the "Can I make it?" matcher, and favourites.

## How "Can I make it?" works

The free TheCocktailDB key cannot search by ingredient (it returns a single sample drink), so `recipes/matching.py` builds its own catalogue and compares each recipe with your bar locally. The catalogue combines the by-letter lists (complete recipes, but each list is capped) with the drinks found by listing every category and glass, looking up any recipe not yet known. Ingredient names are matched by whole words ("rum" matches "Light rum", "gin" does not match "Ginger ale"). Cocktails with nothing missing are listed as makeable now, then those one and two ingredients short with what is missing. Ice and water are assumed to be on hand. Building the catalogue takes about a minute, so it is cached in the database for a week and pre-loaded by `python manage.py warm_catalogue` (run automatically by `build.sh` on deploy). If requests fail while it loads, the page warns that the list may be incomplete and a refresh fills the gaps.

## Favourites

Logged-in users can press Save on any recipe to add it to their favourites (press again to remove it). A favourite stores only the TheCocktailDB drink id, name and picture (`recipes.models.Favourite`, unique per user and drink), so the Favourites page and the dashboard card load without calling the API. Saving is a POST request protected by CSRF and requires login.

## Tech stack

- Django 5.2 (Python), Django templates, Bootstrap 5
- PostgreSQL (SQLite fallback for quick local runs and tests)
- TheCocktailDB external API (recipe search and details)
- Gunicorn + WhiteNoise, deployed on Render

## Project layout

```
config/       project settings, root URLs, WSGI
accounts/     custom User model (email login, role), register/login/logout
core/         landing page and dashboard
templates/    base.html and per-app templates
static/       site CSS
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

## Deploy to Render

1. Push the repository to GitHub.
2. In Render, create a PostgreSQL database, then a new Web Service from the repository.
3. Build command: `bash build.sh` (installs, collects static files, creates the cache table, migrates and pre-loads the cocktail catalogue)   Start command: `gunicorn config.wsgi` (`gunicorn.conf.py` sets a 120 second timeout)
4. Environment variables on the web service:
   - `SECRET_KEY`: a long random string
   - `DEBUG`: `False`
   - `DATABASE_URL`: the Internal Database URL from the Render PostgreSQL instance
   - `ALLOWED_HOSTS`: your Render hostname (Render's `RENDER_EXTERNAL_HOSTNAME` is also added automatically)
5. After the first deploy, create an admin user. The free plan has no Render shell, so run `python manage.py createsuperuser` on your own machine with `DATABASE_URL` temporarily set to the database's External Database URL.

## Security notes

- Passwords are hashed with Django's default PBKDF2 hasher.
- Secrets and database credentials come from environment variables, never from git.
- CSRF protection is on for every form; the dashboard requires login.
- With `DEBUG=False`, HTTPS redirect and secure cookies are enabled.
