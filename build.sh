#!/usr/bin/env bash
# Render build script: install dependencies, collect static files, set up the
# cache table, run migrations and pre-load the cocktail catalogue.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py createcachetable
python manage.py migrate
# Best effort: if the cocktail API is busy the site still deploys.
python manage.py warm_catalogue || true
