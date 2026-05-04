"""Application factory para Flask."""
from flask import Flask, jsonify

from .config import get_settings
from .extensions import cors, db, jwt, migrate, socketio


def create_app(config_overrides: dict | None = None) -> Flask:
    """Arma la app Flask con todas las extensiones registradas."""
    settings = get_settings()
    app = Flask(__name__)

    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = settings.JWT_SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = settings.jwt_access_timedelta
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = settings.jwt_refresh_timedelta

    if config_overrides:
        app.config.update(config_overrides)

    # Extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": settings.cors_origins_list}})
    socketio.init_app(app, cors_allowed_origins=settings.cors_origins_list)

    # Importar modelos para que SQLAlchemy los registre en el metadata
    from . import models  # noqa: F401

    # Blueprints (se registran lazy para evitar ciclos)
    from .api.v1 import register_blueprints

    register_blueprints(app)

    # Error handlers (JSON consistente)
    from .utils.errors import register_error_handlers

    register_error_handlers(app)

    # Namespaces SocketIO
    from .sockets.prices import register_prices_namespace

    register_prices_namespace()

    # CLI commands
    from .seeds import register_cli_commands

    register_cli_commands(app)

    from .cli import register_all as register_cli_all

    register_cli_all(app)

    # Health
    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", app=settings.APP_NAME)

    return app
