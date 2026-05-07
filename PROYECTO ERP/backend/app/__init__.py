"""Application factory para Flask."""
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from .config import get_settings
from .extensions import cors, db, jwt, migrate, socketio

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_FRONTEND_DIST = (_BACKEND_ROOT.parent / "frontend" / "dist").resolve()


def create_app(config_overrides: dict | None = None) -> Flask:
    """Arma la app Flask con todas las extensiones registradas."""
    settings = get_settings()
    frontend_dist = Path(
        os.environ.get("FRONTEND_DIST", str(_DEFAULT_FRONTEND_DIST))
    ).resolve()
    # `URL_PREFIX` (sin trailing slash, ej: `/casasalco`) permite que la app
    # corra detrás de un reverse-proxy con prefijo Y también acepte requests
    # sin el prefijo (acceso local directo). El frontend buildado con
    # `vite.config.ts:base="/casasalco/"` apunta sus assets y XHRs al prefix,
    # pero el HTML servido en local (sin prefix) también necesita resolver
    # esos paths — por eso strippeamos en before_request.
    url_prefix = (os.environ.get("URL_PREFIX") or "").rstrip("/")
    app = Flask(
        __name__,
        static_folder=str(frontend_dist) if frontend_dist.is_dir() else None,
        static_url_path="/__static__",
    )

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

    # Strip del prefijo configurable. Tiene que ser WSGI middleware (no
    # `before_request`) porque Flask hace el routing ANTES del dispatch:
    # cualquier reescritura de PATH_INFO desde un handler se aplica tarde.
    # Idempotente y noop si url_prefix="".
    if url_prefix:

        class _StripPrefix:
            def __init__(self, wsgi_app, prefix):
                self.wsgi_app = wsgi_app
                self.prefix = prefix

            def __call__(self, environ, start_response):
                path = environ.get("PATH_INFO", "")
                if path == self.prefix or path == self.prefix + "/":
                    environ["PATH_INFO"] = "/"
                    environ["SCRIPT_NAME"] = (
                        environ.get("SCRIPT_NAME", "") + self.prefix
                    )
                elif path.startswith(self.prefix + "/"):
                    environ["PATH_INFO"] = path[len(self.prefix):]
                    environ["SCRIPT_NAME"] = (
                        environ.get("SCRIPT_NAME", "") + self.prefix
                    )
                return self.wsgi_app(environ, start_response)

        app.wsgi_app = _StripPrefix(app.wsgi_app, url_prefix)

        # Acceso local a la raíz (sin prefix): redirigimos al prefix para
        # que el router del SPA (que usa basepath) tome la URL correcta.
        # IMPORTANTE: si el request vino CON prefix, el WSGI middleware
        # strippeó y dejó SCRIPT_NAME=url_prefix. Solo redirigimos cuando
        # SCRIPT_NAME está vacío — sino, loop infinito de redirects.
        from flask import redirect

        @app.before_request
        def _redirect_root_to_prefix():
            script_name = request.environ.get("SCRIPT_NAME", "")
            if (
                request.path == "/"
                and not script_name
                and "text/html" in request.headers.get("Accept", "")
            ):
                return redirect(url_prefix + "/", code=302)
            return None

    # Health
    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", app=settings.APP_NAME)

    # SPA — sirve el frontend buildado desde frontend/dist/.
    # /api/*, /socket.io/* y /healthz quedan registrados arriba; el catch-all
    # devuelve 404 para esos prefijos para que el handler de errores JSON tome.
    if frontend_dist.is_dir():
        from werkzeug.exceptions import NotFound

        @app.get("/")
        def _spa_root():
            return send_from_directory(frontend_dist, "index.html")

        @app.get("/<path:path>")
        def _spa_catch_all(path: str):
            if path.startswith(("api/", "socket.io/")) or path == "healthz":
                raise NotFound()
            requested = (frontend_dist / path).resolve()
            try:
                requested.relative_to(frontend_dist)
            except ValueError:
                return send_from_directory(frontend_dist, "index.html")
            if requested.is_file():
                return send_from_directory(frontend_dist, path)
            return send_from_directory(frontend_dist, "index.html")

    return app
