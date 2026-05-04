"""Paquete de seeds. Registra los subcomandos `flask seed demo` y `flask seed big`.

- `flask seed demo` — seed mínimo idempotente para smoke tests (admin + 4 suc + 5 art).
- `flask seed big`  — seed realista (40 proveedores, ~1500 artículos, 30 días de ventas).

Uso:
    flask seed demo
    flask seed big            # exige DB vacía
    flask seed big --force    # wipe + reseed (PELIGROSO, DEV-ONLY)
"""
from __future__ import annotations

import click
from flask import Flask
from flask.cli import AppGroup

from .big import seed_big
from .demo import seed_demo


def register_cli_commands(app: Flask) -> None:
    """Registra `flask seed demo` y `flask seed big` en el AppGroup `seed`."""
    seed_group = AppGroup("seed", help="Comandos de seed de datos.")

    @seed_group.command("demo")
    def _demo_cmd() -> None:
        """Seed mínimo (admin + 4 sucursales + 5 artículos + stock 100u)."""
        seed_demo()
        click.echo("Seed demo aplicado.")

    @seed_group.command("big")
    @click.option(
        "--force",
        is_flag=True,
        help="Wipea todo y re-sembra desde cero (PELIGROSO, DEV-ONLY).",
    )
    def _big_cmd(force: bool) -> None:
        """Seed realista para demos con volumen argentino."""
        seed_big(force=force)

    app.cli.add_command(seed_group)


__all__ = ["register_cli_commands", "seed_demo", "seed_big"]
