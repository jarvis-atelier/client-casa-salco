"""Comandos CLI registrados en la app."""
from __future__ import annotations

from flask import Flask

from .alerts import register_alerts_cli
from .analytics import register_analytics_cli


def register_all(app: Flask) -> None:
    register_alerts_cli(app)
    register_analytics_cli(app)
