"""WSGI-entrypoint voor productie-hosting (bijv. Render, via gunicorn).

Lokaal gebruik gaat via `app.desktop` / `app.webapp.run_dev` — dit bestand is puur voor
een echte productie-WSGI-server die een kant-en-klaar `app`-object verwacht.
"""
from app.webapp.server import create_app

app = create_app()
