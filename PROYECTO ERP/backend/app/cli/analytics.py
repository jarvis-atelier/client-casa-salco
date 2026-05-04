"""CLI para correr analíticas: `flask analytics run`."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import click
from flask import Flask
from flask.cli import AppGroup

from app.extensions import db


def register_analytics_cli(app: Flask) -> None:
    grp = AppGroup("analytics", help="Pre-cálculos de analítica avanzada.")

    @grp.command("run")
    @click.option(
        "--soporte",
        default=0.01,
        show_default=True,
        type=float,
        help="Soporte mínimo Apriori (0..1).",
    )
    @click.option(
        "--confianza",
        default=0.30,
        show_default=True,
        type=float,
        help="Confianza mínima de las reglas (0..1).",
    )
    @click.option(
        "--lift",
        default=1.5,
        show_default=True,
        type=float,
        help="Lift mínimo de las reglas.",
    )
    @click.option(
        "--ventana-dias",
        default=90,
        show_default=True,
        type=int,
        help="Ventana de tiempo a analizar.",
    )
    @click.option(
        "--top",
        default=50,
        show_default=True,
        type=int,
        help="Cantidad máxima de reglas a mostrar.",
    )
    @click.option(
        "--sucursal-id",
        default=None,
        type=int,
        help="Filtrar por sucursal (opcional).",
    )
    def _run(
        soporte: float,
        confianza: float,
        lift: float,
        ventana_dias: int,
        top: int,
        sucursal_id: int | None,
    ) -> None:
        """Calcula correlaciones de productos (Apriori) y las imprime."""
        from app.services.analytics.correlaciones import calcular_correlaciones

        hasta = date.today()
        desde = hasta - timedelta(days=ventana_dias)

        click.echo(
            click.style(
                f"Calculando correlaciones {desde} -> {hasta} "
                f"(sop={soporte} conf={confianza} lift={lift})...",
                fg="cyan",
            )
        )
        t0 = datetime.utcnow()
        result = calcular_correlaciones(
            db.session,
            fecha_desde=desde,
            fecha_hasta=hasta,
            sucursal_id=sucursal_id,
            soporte_min=soporte,
            confianza_min=confianza,
            lift_min=lift,
            top_n=top,
        )
        elapsed = (datetime.utcnow() - t0).total_seconds()

        click.echo(
            click.style(
                f"Listo en {elapsed:.2f}s · "
                f"{result['transacciones_analizadas']} transacciones · "
                f"{result['items_unicos']} items únicos · "
                f"{len(result['reglas'])} reglas",
                fg="green",
                bold=True,
            )
        )

        if not result["reglas"]:
            click.echo(
                click.style(
                    "  No se encontraron reglas con esos thresholds.",
                    fg="yellow",
                )
            )
            return

        for i, r in enumerate(result["reglas"][:20], 1):
            ant = " + ".join(r["antecedentes_desc"])
            cons = " + ".join(r["consecuentes_desc"])
            click.echo(
                f"  {i:2d}. [{', '.join(r['antecedentes_codigos'])}] {ant} "
                f"-> [{', '.join(r['consecuentes_codigos'])}] {cons}"
            )
            click.echo(
                f"      lift={r['lift']:.2f} · confianza={r['confianza']:.1%} · "
                f"soporte={r['soporte']:.1%}"
            )

    app.cli.add_command(grp)
