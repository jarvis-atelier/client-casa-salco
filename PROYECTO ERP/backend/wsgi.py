"""Entry point WSGI — apuntado por FLASK_APP y por gunicorn en produccion.

Produccion (gunicorn + gevent):
    gunicorn --bind 0.0.0.0:8080 --worker-class gevent --workers 1 wsgi:app

Dev local (SocketIO con reloader):
    python wsgi.py
"""
import os

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    # Dev only - en prod gunicorn invoca `app` directamente.
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=debug,
        allow_unsafe_werkzeug=debug,
    )
