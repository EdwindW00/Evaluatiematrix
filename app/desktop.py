"""Opstartpunt: start de Flask-server en opent automatisch de browser.

Gebruik: `python -m app.desktop` vanuit de projectroot (met geactiveerde venv).
"""
from __future__ import annotations

import threading
import webbrowser

from app.webapp.server import create_app

HOST = "127.0.0.1"
PORT = 5151


def main() -> None:
    app = create_app()
    threading.Timer(1.0, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    app.run(host=HOST, port=PORT, threaded=True, debug=False)


if __name__ == "__main__":
    main()
