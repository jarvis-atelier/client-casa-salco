"""Flask app factory for the Jarvis POS Agent."""
from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from .api.routes import register_routes
from .config import Settings, get_settings
from .printer.base import IPrinterDriver
from .printer.factory import get_printer
from .scale.base import IScaleDriver
from .scale.factory import get_scale


def create_app(
    settings: Settings | None = None,
    *,
    printer_driver: IPrinterDriver | None = None,
    scale_driver: IScaleDriver | None = None,
) -> Flask:
    """Build the Flask app. Optional `*_driver` args allow tests to inject."""
    settings = settings or get_settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["SETTINGS"] = settings

    CORS(
        app,
        resources={r"/*": {"origins": settings.cors_origins_list}},
        supports_credentials=False,
    )

    driver = printer_driver or get_printer(settings)
    app.extensions["printer_driver"] = driver

    scale = scale_driver or get_scale(settings)
    app.extensions["scale_driver"] = scale

    register_routes(app)

    @app.errorhandler(404)
    def _not_found(_e):  # type: ignore[no-untyped-def]
        return {"error": "not_found"}, 404

    @app.errorhandler(500)
    def _error(_e):  # type: ignore[no-untyped-def]
        logging.exception("unhandled error")
        return {"error": "internal_error"}, 500

    return app
