"""Migra datos desde SQLite local hacia Postgres remoto.

Uso:
    python scripts/migrate_sqlite_to_postgres.py \\
        --sqlite backend/instance/casasalco.db \\
        --postgres "postgresql+psycopg://user:pass@host:5432/jarvis" \\
        [--truncate] [--dry-run]

Pre-requisitos:
    - Postgres destino YA debe tener el schema creado (ejecutar `flask db upgrade` antes).
    - El script asume que las tablas en SQLite y Postgres tienen la misma estructura.
    - SE RECOMIENDA hacer backup del Postgres destino antes de correr esto.

Estrategia:
    1. Itera tablas en orden FK-safe (padres primero, hijos despues).
    2. Lee filas en batches y las inserta tal cual.
    3. Al final, resetea las sequences (SERIAL) al MAX(id) de cada tabla.

Ojo:
    - Si las tablas tienen columnas con nombres reservados de Postgres, hay que quotearlas.
      Aca usamos cols sin quote por simplicidad - revisar si surgen errores.
    - SQLite serializa booleans como 0/1 enteros. SQLAlchemy los traduce, pero si pegamos
      INSERT directo puede fallar contra Postgres BOOLEAN. Click intentar primero asi y si
      falla, agregar conversion explicita.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Orden FK-safe: padres primero, hijos despues.
# Ajustar segun el schema final del backend (revisar app/models/).
TABLE_ORDER = [
    # Config global
    "comercio_config",
    # Auth y estructura organizacional
    "users",
    "sucursales",
    "areas",
    # Catalogo - jerarquia
    "familias",
    "rubros",
    "subrubros",
    "marcas",
    # Terceros
    "proveedores",
    "clientes",
    # Productos y relaciones
    "articulos",
    "articulos_proveedores",
    # Stock y precios por sucursal
    "stock_sucursal",
    "precios_sucursal",
    "precios_historico",
    # Facturacion
    "facturas",
    "factura_items",
    "factura_pagos",
    "caes",
    # Movimientos y misc
    "movimientos_caja",
    "alertas",
    "comprobantes_ocr",
    # Alembic siempre al final
    "alembic_version",
]

BATCH_SIZE = 500


def _check_engines(src_engine, dst_engine) -> None:
    """Smoke test: ambos engines deben conectar."""
    try:
        with src_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        click.secho(f"ERROR: no se pudo conectar a SQLite: {e}", fg="red", err=True)
        sys.exit(1)

    try:
        with dst_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        click.secho(f"ERROR: no se pudo conectar a Postgres: {e}", fg="red", err=True)
        sys.exit(1)


def _truncate_all(dst_engine) -> None:
    """TRUNCATE CASCADE en orden inverso (hijos primero)."""
    click.secho("Truncating destination tables...", fg="yellow")
    with Session(dst_engine) as s:
        for t in reversed(TABLE_ORDER):
            try:
                s.execute(text(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE"))
                click.echo(f"  truncated {t}")
            except SQLAlchemyError as e:
                # Tabla no existe - skip silencioso
                click.secho(f"  skip {t} ({e.__class__.__name__})", fg="yellow")
                s.rollback()
        s.commit()


def _copy_table(src_engine, dst_engine, table_name: str, dry_run: bool) -> int:
    """Copia una tabla en batches. Devuelve cantidad de filas copiadas."""
    src_inspect = inspect(src_engine)
    if not src_inspect.has_table(table_name):
        click.secho(f"  skip {table_name} (no existe en SQLite)", fg="yellow")
        return 0

    dst_inspect = inspect(dst_engine)
    if not dst_inspect.has_table(table_name):
        click.secho(f"  skip {table_name} (no existe en Postgres)", fg="yellow")
        return 0

    total = 0
    with Session(src_engine) as s_src:
        result = s_src.execute(text(f"SELECT * FROM {table_name}")).mappings()
        rows = list(result)

    if not rows:
        click.echo(f"  {table_name}: 0 rows (vacia)")
        return 0

    if dry_run:
        click.echo(f"  [dry-run] {table_name}: {len(rows)} rows would be inserted")
        return len(rows)

    cols = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    cols_sql = ", ".join(cols)
    ins = text(f"INSERT INTO {table_name} ({cols_sql}) VALUES ({placeholders})")

    # Batch insert
    with Session(dst_engine) as s_dst:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = [dict(r) for r in rows[i : i + BATCH_SIZE]]
            try:
                s_dst.execute(ins, batch)
                s_dst.commit()
                total += len(batch)
            except SQLAlchemyError as e:
                s_dst.rollback()
                click.secho(
                    f"  ERROR insertando batch en {table_name}: {e}", fg="red", err=True
                )
                raise

    click.secho(f"  {table_name}: {total} rows", fg="green")
    return total


def _reset_sequences(dst_engine) -> None:
    """Resetea sequences SERIAL al max(id) de cada tabla."""
    click.secho("Reseting Postgres sequences...", fg="cyan")
    dst_inspect = inspect(dst_engine)
    with Session(dst_engine) as s:
        for table_name in TABLE_ORDER:
            if not dst_inspect.has_table(table_name):
                continue
            # Solo si tiene columna 'id' con sequence asociada
            try:
                result = s.execute(
                    text(
                        f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table_name}', 'id'),
                            COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                            (SELECT MAX(id) IS NOT NULL FROM {table_name})
                        )
                        """
                    )
                ).scalar()
                if result is not None:
                    click.echo(f"  {table_name}.id sequence -> {result}")
            except SQLAlchemyError:
                # Tabla sin sequence (alembic_version, tablas asociativas) - skip
                s.rollback()
        s.commit()


@click.command()
@click.option(
    "--sqlite",
    "sqlite_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path al archivo SQLite origen",
)
@click.option(
    "--postgres",
    "postgres_url",
    required=True,
    help="URL Postgres destino (postgresql+psycopg://user:pass@host:5432/db)",
)
@click.option(
    "--truncate",
    is_flag=True,
    help="TRUNCATE CASCADE todas las tablas destino antes de migrar",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="No inserta nada, solo muestra cuantas filas se moverian",
)
def main(sqlite_path: str, postgres_url: str, truncate: bool, dry_run: bool) -> None:
    """Migra SQLite -> Postgres respetando FK order y reseteando sequences."""
    sqlite_path = str(Path(sqlite_path).resolve())
    src_engine = create_engine(f"sqlite:///{sqlite_path}")
    dst_engine = create_engine(postgres_url)

    click.secho(f"Source : sqlite:///{sqlite_path}", fg="cyan")
    click.secho(f"Target : {postgres_url.split('@')[-1] if '@' in postgres_url else postgres_url}", fg="cyan")
    click.secho(f"Mode   : {'DRY-RUN' if dry_run else 'WRITE'}", fg="cyan")
    click.echo("")

    _check_engines(src_engine, dst_engine)

    if truncate and not dry_run:
        if not click.confirm("Esto borrara TODOS los datos del Postgres destino. Continuar?"):
            click.secho("Cancelado.", fg="yellow")
            return
        _truncate_all(dst_engine)

    click.secho("Copying tables...", fg="cyan")
    grand_total = 0
    for table_name in TABLE_ORDER:
        grand_total += _copy_table(src_engine, dst_engine, table_name, dry_run)

    if not dry_run:
        _reset_sequences(dst_engine)

    click.echo("")
    click.secho(
        f"Migracion {'simulada' if dry_run else 'completada'}: {grand_total} rows totales.",
        fg="green",
        bold=True,
    )


if __name__ == "__main__":
    main()
