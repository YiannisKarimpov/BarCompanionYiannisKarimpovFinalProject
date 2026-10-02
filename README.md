# Bar Companion

A cocktail and bar-management web app for bartenders, built with Django and PostgreSQL as the final project for the UCD Dublin Professional Academy Full Stack Software Development course.

Users can register and log in, then (as features are added week by week) browse cocktail recipes from an external API, track their bar's stock, see which cocktails they can make, save favourites, and build costed menus.

## Status

Week 2 skeleton: project structure, custom email-based user model, registration, login, logout, landing page, protected dashboard, automated tests, and deployment configuration.

## Tech stack

- Django 5.2 (Python), Django templates, Bootstrap 5
- PostgreSQL (SQLite fallback for quick local runs and tests)
- TheCocktailDB external API (planned, week 4)
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

3. Apply migrations, create an admin user, and start the server:

   ```
   python manage.py migrate
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
3. Build command: `bash build.sh`   Start command: `gunicorn config.wsgi`
4. Environment variables on the web service:
   - `SECRET_KEY`: a long random string
   - `DEBUG`: `False`
   - `DATABASE_URL`: the Internal Database URL from the Render PostgreSQL instance
   - `ALLOWED_HOSTS`: your Render hostname (Render's `RENDER_EXTERNAL_HOSTNAME` is also added automatically)
5. After the first deploy, open the Render shell and run `python manage.py createsuperuser`.

## Security notes

- Passwords are hashed with Django's default PBKDF2 hasher.
- Secrets and database credentials come from environment variables, never from git.
- CSRF protection is on for every form; the dashboard requires login.
- With `DEBUG=False`, HTTPS redirect and secure cookies are enabled.
