"""
Django settings for Bar Companion.

Configuration that differs between machines (secret key, debug flag, database,
allowed hosts) is read from environment variables via python-decouple, so no
secrets are committed to git. See .env.example for the variables.
"""
import sys
from pathlib import Path

import dj_database_url
from decouple import Csv, config
from django.contrib import messages

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core ---------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY", default="dev-only-insecure-key-change-me")
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
# Render exposes the public hostname of the service in this variable.
RENDER_HOST = config("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)

CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host not in ("localhost", "127.0.0.1")]

# --- Applications -------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "core",
    "bar",
    "recipes",
    "menus",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database -----------------------------------------------------------
# DATABASE_URL points at PostgreSQL in development and on Render, e.g.
# postgres://user:password@localhost:5432/barcompanion
# If it is not set, SQLite is used so the project still runs and tests anywhere.
DATABASES = {
    "default": dj_database_url.config(
        default=config("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

# --- Authentication -----------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
# Passwords are hashed with Django's default PBKDF2 hasher.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "core:home"

# --- Internationalisation ----------------------------------------------
LANGUAGE_CODE = "en-ie"
TIME_ZONE = "Europe/Dublin"
USE_I18N = True
USE_TZ = True

# --- Static files -------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# The manifest storage needs collectstatic to have run, so the test runner
# (which forces DEBUG off) uses plain static file storage instead.
RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == "test"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if RUNNING_TESTS
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cache ---------------------------------------------------------------
# API responses (and the assembled cocktail catalogue) are cached in the
# database so they survive restarts and are shared by every worker. Create the
# table once with ``python manage.py createcachetable``. Tests use memory.
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
        if RUNNING_TESTS
        else {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache",
            "OPTIONS": {"MAX_ENTRIES": 5000},
        }
    )
}

# --- TheCocktailDB external API ----------------------------------------
# "1" is the free test key, fine for development. Check the API's terms and
# use a production key before a public release.
COCKTAILDB_API_KEY = config("COCKTAILDB_API_KEY", default="1")
COCKTAILDB_BASE_URL = config("COCKTAILDB_BASE_URL", default="https://www.thecocktaildb.com/api/json/v1")

# Map Django message levels onto Bootstrap alert classes.
MESSAGE_TAGS = {messages.ERROR: "danger"}

# --- Production security (only when DEBUG is off) ----------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # tell browsers to use HTTPS only, for 30 days
