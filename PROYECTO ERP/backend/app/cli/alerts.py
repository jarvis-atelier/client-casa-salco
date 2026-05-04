"""CLI para correr detectores de alertas: `flask alerts run`."""
from __future__ import annotations

import click
from flask import Flask
from flask.cli import AppGroup

from app.extensions import db


def register_alerts_cli(app: Flask) -> None:
    alerts_group = AppGroup("alerts", help="Detección de inconsistencias.")

    @alerts_group.command("run")
    @click.option(
        "--ventana-dias",
        default=90,
        show_default=True,
        type=int,
        help="Ventana de tiempo a inspeccionar (días).",
    )
    def _run(ventana_dias: int) -> None:
        """Corre todos los detectores y crea alertas nuevas (idempotente)."""
        from app.services.alerts.runner import run_all_detectors

        result = run_all_detectors(db.session, ventana_dias=ventana_dias)
        click.echo(
            click.style(
                f"Alertas nuevas creadas: {result['creadas']} "
                f"(detectores corridos: {result['detectores']})",
                fg="green",
                bold=True,
            )
        )
        for tipo, n in result["detalle"].items():
            click.echo(f"  {tipo}: {n}")

    app.cli.add_command(alerts_group)
