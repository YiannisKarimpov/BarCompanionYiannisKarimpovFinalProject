"""Gunicorn settings (gunicorn reads this file automatically from the project root).

The longer timeout is a safety net for the rare request that has to rebuild the
cocktail catalogue because the cache expired or was cleared.
"""
timeout = 120
