"""`python -m jarvis_agent` entrypoint — runs the Flask dev server.

For Windows-service deployment we'll wrap this with `pywin32` later.
"""
from __future__ import annotations

import logging

from .app import create_app
from .config import get_settings


def main() -> None:
    settings = get_settings()
    app = create_app(settings)

    logging.getLogger().info(
        "Jarvis POS Agent listo en http://%s:%d (driver=%s)",
        settings.JARVIS_AGENT_HOST,
        settings.JARVIS_AGENT_PORT,
        settings.PRINTER_MODE,
    )

    # Use Werkzeug dev server. For prod, wrap in waitress / gunicorn.
    app.run(
        host=settings.JARVIS_AGENT_HOST,
        port=settings.JARVIS_AGENT_PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
