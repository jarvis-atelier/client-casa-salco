"""Seed realista (`flask seed big`) — genera dataset "big demo" para almacén argentino.

Objetivo:
- 40 proveedores con CUIT válido
- 10 familias, ~47 rubros, ~140 subrubros
- 100+ marcas
- ~1500 artículos (combinaciones marca × subrubro × presentación)
- Precios por sucursal (pvp_base en todas)
- Stock: ~6000 filas (1500 art × 4 suc) con distribución realista
- 30 clientes + consumidor final
- 8 usuarios (admin existente + 4 cajeros + 2 supervisores + 1 contador)
- 300-600 facturas distribuidas en últimos 30 días con patrones reales

Idempotencia:
- Por defecto, si ya hay artículos > 50, imprime warning y sale (no hace nada).
- Con --force, wipea las tablas afectadas en orden FK-safe y re-sembra.

Perf target: <2 minutos. Usa `bulk_save_objects` / `session.execute(insert(...))`
para insertar en lote.
"""
from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import click
from faker import Faker
from sqlalchemy import delete, insert, select, text

from app.extensions import db
from app.models.articulo import Articulo, ArticuloProveedor, UnidadMedidaEnum
from app.models.articulo_codigo import ArticuloCodigo, TipoCodigoArticuloEnum
from app.models.cae import Cae
from app.models.categorias import Familia, Marca, Rubro, Subrubro
from app.models.cliente import Cliente, CondicionIvaEnum
from app.models.factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)
from app.models.factura_item import FacturaItem
from app.models.pago import FacturaPago, MedioPagoEnum
from app.models.precio import PrecioHistorico, PrecioSucursal
from app.models.proveedor import Proveedor
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.models.stock import StockSucursal
from app.models.sucursal import Area, Sucursal
from app.models.user import RolEnum, User
from app.services.auth_service import hash_password

from .data.marcas import MARCAS, MARCAS_POR_FAMILIA
from .data.precios_presentaciones import CONFIG as PRECIOS_CONFIG
from .data.precios_presentaciones import PROVEEDOR_POR_FAMILIA
from .data.proveedores import PROVEEDORES
from .data.taxonomia import FAMILIAS, RUBROS, SUBRUBROS

# -------- helpers

SEED = 42
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


def _round2(v: Decimal) -> Decimal:
    return v.quantize(Q2, rounding=ROUND_HALF_UP)


def _round4(v: Decimal) -> Decimal:
    return v.quantize(Q4, rounding=ROUND_HALF_UP)


def _dec(v: float | int | str) -> Decimal:
    return Decimal(str(v))


# -------- EAN-13 con dígito verificador válido

def _ean13(prefix: str, body: str) -> str:
    """Genera un EAN-13 con dígito verificador válido.

    prefix (3) + body (9) = 12 dígitos; el 13º es el check digit.
    """
    assert len(prefix) == 3 and len(body) == 9
    base = prefix + body
    total = 0
    for i, ch in enumerate(base):
        d = int(ch)
        total += d if i % 2 == 0 else d * 3
    check = (10 - (total % 10)) % 10
    return base + str(check)


def _cuit(tipo: str, dni: str) -> str:
    """CUIT con DV válido (tipo + 8 dígitos)."""
    base = tipo + dni
    weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(base, weights))
    mod = total % 11
    dv = 11 - mod
    if dv == 11:
        dv = 0
    elif dv == 10:
        dv = 9
    return f"{tipo}-{dni}-{dv}"


# -------- datos sucursales (mismos que demo)

_SUCURSALES = [
    {"codigo": "SUC01", "nombre": "CASA SALCO Centro", "direccion": "Av. San Martín 1200",
     "ciudad": "Rio Cuarto", "provincia": "Cordoba", "tiene_fiambre": True, "peso": 0.35},
    {"codigo": "SUC02", "nombre": "CASA SALCO Norte", "direccion": "Av. Mitre 450",
     "ciudad": "Rio Cuarto", "provincia": "Cordoba", "tiene_fiambre": True, "peso": 0.30},
    {"codigo": "SUC03", "nombre": "CASA SALCO Sur", "direccion": "Bv. Roca 890",
     "ciudad": "Rio Cuarto", "provincia": "Cordoba", "tiene_fiambre": False, "peso": 0.20},
    {"codigo": "SUC04", "nombre": "CASA SALCO Express", "direccion": "Av. España 210",
     "ciudad": "Rio Cuarto", "provincia": "Cordoba", "tiene_fiambre": True, "peso": 0.15},
]

_AREAS_BASE = [
    ("COM", "Comestibles", 10),
    ("FIA", "Fiambrería", 20),
    ("POL", "Pollería", 30),
    ("DRU", "Drugstore", 40),
]


# -------- Wipe (para --force)

# Orden FK-safe: primero todo lo que referencia a facturas/articulos/etc.
_WIPE_ORDER = [
    "movimientos_caja",
    "factura_pagos",
    "factura_items",
    "caes",
    "facturas",
    "precios_historicos",
    "precios_sucursal",
    "stock_sucursal",
    "articulo_proveedores",
    "articulo_codigos",
    "articulos",
    "subrubros",
    "rubros",
    "familias",
    "marcas",
    "proveedores",
    "clientes",
]


def _wipe(echo) -> None:
    """Borra todo el dataset grande en orden FK-safe.

    NO borra `users` (queda admin) ni `sucursales` ni `areas` (queda la config).
    """
    echo("Wipeando tablas (FK-safe)...")
    for tbl in _WIPE_ORDER:
        db.session.execute(text(f"DELETE FROM {tbl}"))
    # Usuarios no-admin también se borran (para dejar sólo al admin original)
    db.session.execute(
        db.text("DELETE FROM users WHERE email != 'admin@casasalco.app'")
    )
    db.session.commit()


# -------- Seed principal


@dataclass
class Counts:
    proveedores: int = 0
    familias: int = 0
    rubros: int = 0
    subrubros: int = 0
    marcas: int = 0
    articulos: int = 0
    articulo_proveedores: int = 0
    precios_sucursal: int = 0
    stock_rows: int = 0
    clientes: int = 0
    users: int = 0
    facturas_30d: int = 0
    items_totales: int = 0
    movimientos_caja: int = 0
    pagos_totales: int = 0
    caes: int = 0


def seed_big(force: bool = False) -> None:
    """Entry point del seed big."""
    random.seed(SEED)
    Faker.seed(SEED)
    fake = Faker("es_AR")

    t0 = time.perf_counter()
    counts = Counts()
    echo = click.echo

    # --- Idempotencia / force
    existing_art = db.session.execute(select(Articulo.id).limit(60)).all()
    if existing_art and len(existing_art) > 50 and not force:
        echo(click.style(
            "WARN: ya hay >50 artículos. El seed big es idempotente: "
            "no hace nada. Usá --force para borrar y re-sembrar.",
            fg="yellow",
        ))
        return

    if force:
        _wipe(echo)

    # --- 1) Admin + sucursales + áreas (idempotente)
    _ensure_admin(echo)
    suc_by_code = _ensure_sucursales_y_areas(echo)

    # --- 2) Proveedores
    proveedores = _seed_proveedores(echo)
    counts.proveedores = len(proveedores)

    # --- 3) Familias / Rubros / Subrubros
    familias, rubros, subrubros = _seed_taxonomia(echo)
    counts.familias = len(familias)
    counts.rubros = len(rubros)
    counts.subrubros = len(subrubros)

    # --- 4) Marcas
    marcas = _seed_marcas(echo)
    counts.marcas = len(marcas)

    # --- 5) Artículos (genera ~1500 combinaciones)
    articulos = _seed_articulos(echo, familias, rubros, subrubros, marcas, proveedores, fake)
    counts.articulos = len(articulos)

    # --- 6) Articulo-Proveedor (1-3 por artículo)
    counts.articulo_proveedores = _seed_articulo_proveedor(echo, articulos, proveedores)

    # --- 7) Precios por sucursal
    counts.precios_sucursal = _seed_precios_sucursal(echo, articulos, suc_by_code)

    # --- 8) Stock inicial con distribución realista + defaults globales
    counts.stock_rows = _seed_stock(echo, articulos, suc_by_code)
    _seed_articulos_defaults_stock(echo, articulos)

    # --- 9) Clientes (30 + CF)
    counts.clientes = _seed_clientes(echo, fake)

    # --- 10) Usuarios adicionales
    counts.users = _seed_users(echo, suc_by_code)

    # --- 11) Historial de ventas últimos 30 días
    fac, items, pagos, movs, caes = _seed_historial_ventas(
        echo, articulos, suc_by_code, fake
    )
    counts.facturas_30d = fac
    counts.items_totales = items
    counts.pagos_totales = pagos
    counts.movimientos_caja = movs
    counts.caes = caes

    elapsed = time.perf_counter() - t0

    # Final summary
    echo("")
    echo(click.style("=" * 60, fg="green"))
    echo(click.style("SEED BIG — RESUMEN", fg="green", bold=True))
    echo(click.style("=" * 60, fg="green"))
    echo(f"  proveedores:          {counts.proveedores}")
    echo(f"  familias:             {counts.familias}")
    echo(f"  rubros:               {counts.rubros}")
    echo(f"  subrubros:            {counts.subrubros}")
    echo(f"  marcas:               {counts.marcas}")
    echo(f"  articulos:            {counts.articulos}")
    echo(f"  articulo_proveedores: {counts.articulo_proveedores}")
    echo(f"  precios_sucursal:     {counts.precios_sucursal}")
    echo(f"  stock_rows:           {counts.stock_rows}")
    echo(f"  clientes:             {counts.clientes}")
    echo(f"  usuarios:             {counts.users}")
    echo(f"  facturas (30 días):   {counts.facturas_30d}")
    echo(f"  items:                {counts.items_totales}")
    echo(f"  pagos:                {counts.pagos_totales}")
    echo(f"  movimientos_caja:     {counts.movimientos_caja}")
    echo(f"  caes:                 {counts.caes}")
    echo(click.style("-" * 60, fg="green"))
    echo(f"  Duración: {elapsed:.1f}s")
    echo(click.style("=" * 60, fg="green"))


# =========================================================
# Subseeds
# =========================================================


def _ensure_admin(echo) -> None:
    admin = db.session.query(User).filter(User.email == "admin@casasalco.app").first()
    if admin is None:
        admin = User(
            email="admin@casasalco.app",
            password_hash=hash_password("admin123"),
            nombre="Administrador Demo",
            rol=RolEnum.admin,
            activo=True,
        )
        db.session.add(admin)
        db.session.commit()
    echo(f"admin OK (id={admin.id})")


def _ensure_sucursales_y_areas(echo) -> dict[str, Sucursal]:
    suc_by_code: dict[str, Sucursal] = {}
    for data in _SUCURSALES:
        suc = db.session.query(Sucursal).filter(Sucursal.codigo == data["codigo"]).first()
        if suc is None:
            suc = Sucursal(
                codigo=data["codigo"],
                nombre=data["nombre"],
                direccion=data["direccion"],
                ciudad=data["ciudad"],
                provincia=data["provincia"],
                activa=True,
            )
            db.session.add(suc)
        suc_by_code[data["codigo"]] = suc
    db.session.flush()

    for data in _SUCURSALES:
        suc = suc_by_code[data["codigo"]]
        for codigo, nombre, orden in _AREAS_BASE:
            if codigo == "FIA" and not data["tiene_fiambre"]:
                continue
            exists = (
                db.session.query(Area)
                .filter(Area.sucursal_id == suc.id, Area.codigo == codigo)
                .first()
            )
            if exists is None:
                db.session.add(
                    Area(
                        sucursal_id=suc.id,
                        codigo=codigo,
                        nombre=nombre,
                        orden=orden,
                        activa=True,
                    )
                )
    db.session.commit()
    echo(f"sucursales OK ({len(suc_by_code)})")
    return suc_by_code


def _seed_proveedores(echo) -> list[Proveedor]:
    rows = []
    for p in PROVEEDORES:
        exists = (
            db.session.query(Proveedor).filter(Proveedor.codigo == p["codigo"]).first()
        )
        if exists is None:
            rows.append(
                {
                    "codigo": p["codigo"],
                    "razon_social": p["razon_social"],
                    "cuit": p["cuit"],
                    "activo": True,
                }
            )
    if rows:
        db.session.execute(insert(Proveedor), rows)
        db.session.commit()

    out = db.session.query(Proveedor).order_by(Proveedor.id).all()
    echo(f"proveedores OK ({len(out)})")
    return out


def _seed_taxonomia(echo) -> tuple[dict, dict, dict]:
    # Familias
    fam_rows = []
    for codigo, nombre, orden in FAMILIAS:
        if db.session.query(Familia).filter(Familia.codigo == codigo).first() is None:
            fam_rows.append({"codigo": codigo, "nombre": nombre, "orden": orden})
    if fam_rows:
        db.session.execute(insert(Familia), fam_rows)
        db.session.commit()

    familias: dict[str, Familia] = {
        f.codigo: f for f in db.session.query(Familia).all()
    }

    # Rubros
    rubro_rows = []
    for fam_cod, cod, nombre in RUBROS:
        fam = familias[fam_cod]
        if (
            db.session.query(Rubro)
            .filter(Rubro.familia_id == fam.id, Rubro.codigo == cod)
            .first()
            is None
        ):
            rubro_rows.append(
                {
                    "familia_id": fam.id,
                    "codigo": cod,
                    "nombre": nombre,
                    "orden": 0,
                }
            )
    if rubro_rows:
        db.session.execute(insert(Rubro), rubro_rows)
        db.session.commit()

    rubros: dict[tuple[str, str], Rubro] = {}
    for r in db.session.query(Rubro).all():
        fam = next(f for f in familias.values() if f.id == r.familia_id)
        rubros[(fam.codigo, r.codigo)] = r

    # Subrubros
    sub_rows = []
    for fam_cod, rub_cod, cod, nombre in SUBRUBROS:
        rub = rubros[(fam_cod, rub_cod)]
        if (
            db.session.query(Subrubro)
            .filter(Subrubro.rubro_id == rub.id, Subrubro.codigo == cod)
            .first()
            is None
        ):
            sub_rows.append(
                {
                    "rubro_id": rub.id,
                    "codigo": cod,
                    "nombre": nombre,
                    "orden": 0,
                }
            )
    if sub_rows:
        db.session.execute(insert(Subrubro), sub_rows)
        db.session.commit()

    subrubros: dict[tuple[str, str, str], Subrubro] = {}
    rubro_by_id = {r.id: key for key, r in rubros.items()}
    for s in db.session.query(Subrubro).all():
        fam_cod, rub_cod = rubro_by_id[s.rubro_id]
        subrubros[(fam_cod, rub_cod, s.codigo)] = s

    echo(
        f"taxonomia OK (fam={len(familias)} rub={len(rubros)} sub={len(subrubros)})"
    )
    return familias, rubros, subrubros


def _seed_marcas(echo) -> list[Marca]:
    existing = {m.nombre for m in db.session.query(Marca).all()}
    rows = [
        {"nombre": n, "activa": True} for n in MARCAS if n not in existing
    ]
    if rows:
        db.session.execute(insert(Marca), rows)
        db.session.commit()
    out = db.session.query(Marca).order_by(Marca.id).all()
    echo(f"marcas OK ({len(out)})")
    return out


def _seed_articulos(
    echo,
    familias: dict,
    rubros: dict,
    subrubros: dict,
    marcas: list[Marca],
    proveedores: list[Proveedor],
    fake,
) -> list[Articulo]:
    """Genera artículos combinando marca × subrubro × variante × presentación.

    Objetivo ~1500. Iteramos subrubros y para cada uno elegimos varias marcas
    compatibles con la familia. Cada (marca, variante, presentación) = 1 art.
    """
    existing_cods = {
        c for (c,) in db.session.execute(select(Articulo.codigo)).all()
    }
    # Principales ya existentes en articulo_codigos: tipo='principal'
    # (la columna Articulo.codigo_barras ya no existe — migración a 1:N).
    existing_barras = {
        b for (b,) in db.session.execute(
            select(ArticuloCodigo.codigo).where(
                ArticuloCodigo.tipo == TipoCodigoArticuloEnum.principal
            )
        ).all()
    }

    # mapear proveedor_idx -> Proveedor real (order by id)
    proveedores_ordered = proveedores

    rows: list[dict[str, Any]] = []
    # Mapa natural-key -> codigo principal (EAN-13) que escribiremos en
    # `articulo_codigos` despues del bulk insert de articulos (Pass 2).
    barras_por_codigo: dict[str, str] = {}
    counter_by_rubro: dict[tuple[str, str], int] = {}

    marcas_by_name = {m.nombre: m for m in marcas}
    # Resolver pool de marcas por familia (sólo las que efectivamente existen en DB)
    marcas_pool_por_fam: dict[str, list[Marca]] = {}
    for fam_cod, nombres in MARCAS_POR_FAMILIA.items():
        pool = [marcas_by_name[n] for n in nombres if n in marcas_by_name]
        if not pool:
            # Fallback: usar todas las marcas si no hay pool para esta familia
            pool = list(marcas)
        marcas_pool_por_fam[fam_cod] = pool

    items_plan: list[tuple] = []  # (fam, rubro, sub, marca, variante, pres)
    for key, cfg in PRECIOS_CONFIG.items():
        fam_cod, rub_cod, sub_cod = key
        # sanity: subrubro debe existir
        if key not in subrubros:
            continue
        variantes = cfg.get("variantes") or [None]
        presentaciones = cfg.get("presentaciones") or ["unidad"]

        # Marcas del pool compatible con esta familia
        pool = marcas_pool_por_fam.get(fam_cod, list(marcas))
        marcas_muestra = min(max(len(variantes) * len(presentaciones) // 2, 6), 12)
        marcas_elegidas = random.sample(pool, k=min(marcas_muestra, len(pool)))

        for marca in marcas_elegidas:
            for variante in variantes:
                for presentacion in presentaciones:
                    items_plan.append((fam_cod, rub_cod, sub_cod, marca, variante, presentacion))

    random.shuffle(items_plan)
    # Tomamos hasta ~1500
    target = 1500
    if len(items_plan) > target:
        items_plan = items_plan[:target]

    with click.progressbar(items_plan, label="Artículos") as bar:
        for fam_cod, rub_cod, sub_cod, marca, variante, presentacion in bar:
            cfg = PRECIOS_CONFIG[(fam_cod, rub_cod, sub_cod)]
            familia = familias[fam_cod]
            rubro = rubros[(fam_cod, rub_cod)]
            subrubro = subrubros[(fam_cod, rub_cod, sub_cod)]

            # Código incremental por rubro
            key_ctr = (fam_cod, rub_cod)
            counter_by_rubro[key_ctr] = counter_by_rubro.get(key_ctr, 0) + 1
            seq = counter_by_rubro[key_ctr]
            codigo = f"{fam_cod}-{rub_cod}-{seq:04d}"
            if codigo in existing_cods:
                continue
            existing_cods.add(codigo)

            # EAN-13: prefijo 779 Argentina + 9 dígitos (6 del CRC del código + 3 random)
            # Generamos body a partir del código para reproducibilidad + azar.
            body = f"{random.randint(100000000, 999999999)}"
            barras = _ean13("779", body)
            # evitar colisiones
            while barras in existing_barras:
                body = f"{random.randint(100000000, 999999999)}"
                barras = _ean13("779", body)
            existing_barras.add(barras)

            # Descripción
            parts = [cfg["nombre_producto"], marca.nombre]
            if variante:
                parts.append(variante)
            parts.append(presentacion)
            descripcion = " ".join(parts)
            desc_corta = descripcion[:30]

            # Costo ARS
            costo = random.uniform(cfg["costo_min"], cfg["costo_max"])
            # Markup por familia (heurística realista)
            if fam_cod == "FIA":
                markup = random.uniform(1.40, 1.60)
            elif fam_cod == "ALM":
                markup = random.uniform(1.20, 1.35)
            elif fam_cod == "BSA":
                markup = random.uniform(1.30, 1.45)
            elif fam_cod == "BCA":
                markup = random.uniform(1.30, 1.50)
            elif fam_cod == "LAC":
                markup = random.uniform(1.25, 1.45)
            elif fam_cod == "CAR":
                markup = random.uniform(1.20, 1.35)
            elif fam_cod == "PAN":
                markup = random.uniform(1.30, 1.50)
            elif fam_cod == "LIM":
                markup = random.uniform(1.30, 1.50)
            elif fam_cod == "HIG":
                markup = random.uniform(1.35, 1.55)
            else:
                markup = random.uniform(1.30, 1.50)

            pvp = costo * markup

            # Proveedor principal coherente con familia
            prov_indices = PROVEEDOR_POR_FAMILIA.get(fam_cod, [])
            prov_id = None
            if prov_indices:
                idx = random.choice(prov_indices)
                if idx < len(proveedores_ordered):
                    prov_id = proveedores_ordered[idx].id

            # Activo 95% True
            activo = random.random() > 0.05

            rows.append(
                {
                    "codigo": codigo,
                    "descripcion": descripcion,
                    "descripcion_corta": desc_corta,
                    "familia_id": familia.id,
                    "rubro_id": rubro.id,
                    "subrubro_id": subrubro.id,
                    "marca_id": marca.id,
                    "proveedor_principal_id": prov_id,
                    "unidad_medida": cfg["unidad"],
                    "controla_stock": True,
                    "controla_vencimiento": cfg.get("vencimiento", False),
                    "costo": _round4(_dec(costo)),
                    "pvp_base": _round4(_dec(pvp)),
                    "iva_porc": cfg.get("iva", Decimal("21")),
                    "activo": activo,
                }
            )
            # Pass 2 (post-flush) escribira esto via ArticuloCodigo.
            barras_por_codigo[codigo] = barras

    # --- Pass 1: bulk insert de articulos (sin codigo_barras — la columna
    # ya no existe; el codigo principal va al hijo `articulo_codigos`).
    for i in range(0, len(rows), 500):
        db.session.execute(insert(Articulo), rows[i : i + 500])
    db.session.commit()

    out = db.session.query(Articulo).order_by(Articulo.id).all()

    # --- Pass 2: bulk insert de codigos principales en articulo_codigos.
    # Mapeamos natural-key (codigo) -> articulo.id para zippear con el
    # EAN-13 generado en Pass 1.
    id_por_codigo: dict[str, int] = {a.codigo: a.id for a in out}
    codigo_rows: list[dict[str, Any]] = []
    for codigo_articulo, barras in barras_por_codigo.items():
        art_id = id_por_codigo.get(codigo_articulo)
        if art_id is None:
            # No deberia pasar — el bulk insert es exhaustivo —, pero defensivo.
            continue
        codigo_rows.append(
            {
                "articulo_id": art_id,
                "codigo": barras,
                "tipo": TipoCodigoArticuloEnum.principal.value,
            }
        )
    for i in range(0, len(codigo_rows), 500):
        db.session.execute(insert(ArticuloCodigo), codigo_rows[i : i + 500])
    db.session.commit()

    echo(f"articulos OK ({len(out)})  +  codigos principales ({len(codigo_rows)})")
    return out


def _seed_articulo_proveedor(
    echo, articulos: list[Articulo], proveedores: list[Proveedor]
) -> int:
    rows: list[dict[str, Any]] = []
    n_prov = len(proveedores)
    seen_pairs: set[tuple[int, int]] = set()

    with click.progressbar(articulos, label="Art-Prov") as bar:
        for art in bar:
            # 1-3 proveedores alternativos
            k = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
            # Siempre incluir el principal si existe
            prov_ids: set[int] = set()
            if art.proveedor_principal_id:
                prov_ids.add(art.proveedor_principal_id)
            while len(prov_ids) < k:
                prov_ids.add(proveedores[random.randrange(n_prov)].id)

            for pid in prov_ids:
                pair = (art.id, pid)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                # costo ±5%
                factor = random.uniform(0.95, 1.05)
                costo_prov = _round4(art.costo * _dec(factor))
                rows.append(
                    {
                        "articulo_id": art.id,
                        "proveedor_id": pid,
                        "costo_proveedor": costo_prov,
                        "codigo_proveedor": f"P{pid}-{art.codigo}"[:50],
                        "ultimo_ingreso": None,
                    }
                )

    for i in range(0, len(rows), 500):
        db.session.execute(insert(ArticuloProveedor), rows[i : i + 500])
    db.session.commit()
    echo(f"art-prov OK ({len(rows)})")
    return len(rows)


def _seed_precios_sucursal(
    echo,
    articulos: list[Articulo],
    suc_by_code: dict[str, Sucursal],
) -> int:
    """Un precio activo por (articulo, sucursal) = pvp_base."""
    rows: list[dict[str, Any]] = []
    now = datetime.now(UTC)
    sucursales = list(suc_by_code.values())

    with click.progressbar(articulos, label="Precios") as bar:
        for art in bar:
            for suc in sucursales:
                rows.append(
                    {
                        "articulo_id": art.id,
                        "sucursal_id": suc.id,
                        "precio": art.pvp_base,
                        "vigente_desde": now,
                        "activo": True,
                    }
                )

    for i in range(0, len(rows), 1000):
        db.session.execute(insert(PrecioSucursal), rows[i : i + 1000])
    db.session.commit()
    echo(f"precios_sucursal OK ({len(rows)})")
    return len(rows)


def _seed_stock(
    echo,
    articulos: list[Articulo],
    suc_by_code: dict[str, Sucursal],
) -> int:
    """Stock con distribución realista:
    70%: 5-200 unidades; 20%: 200-500; 5%: 1-4 (bajo); 5%: 0 (agotado).

    Adicionalmente — opción C de stock inteligente — sembra umbrales por
    sucursal para ~30% de los artículos (mín / reorden / máx) y deja el
    resto heredando defaults del articulo (que se setean también en una
    fracción del catálogo via _seed_articulos_defaults_stock).
    """
    rows: list[dict[str, Any]] = []
    sucursales = list(suc_by_code.values())

    with click.progressbar(articulos, label="Stock") as bar:
        for art in bar:
            for suc in sucursales:
                r = random.random()
                if r < 0.70:
                    qty = random.randint(5, 200)
                elif r < 0.90:
                    qty = random.randint(200, 500)
                elif r < 0.95:
                    qty = random.randint(1, 4)
                else:
                    qty = 0

                row = {
                    "articulo_id": art.id,
                    "sucursal_id": suc.id,
                    "cantidad": Decimal(str(qty)),
                }
                # 30% override en sucursal con umbrales
                if random.random() < 0.30:
                    minimo = random.choice([5, 10, 15, 20])
                    reorden = minimo + random.choice([10, 15, 20, 30])
                    maximo = reorden + random.choice([50, 80, 120, 200])
                    row["stock_minimo"] = Decimal(str(minimo))
                    row["punto_reorden"] = Decimal(str(reorden))
                    row["stock_maximo"] = Decimal(str(maximo))
                    row["lead_time_dias"] = random.choice([3, 5, 7, 10])
                rows.append(row)

    for i in range(0, len(rows), 1000):
        db.session.execute(insert(StockSucursal), rows[i : i + 1000])
    db.session.commit()
    echo(f"stock OK ({len(rows)})")
    return len(rows)


def _seed_articulos_defaults_stock(
    echo,
    articulos: list[Articulo],
) -> int:
    """Setea defaults globales de stock inteligente en ~50% de los artículos.

    Para los que NO tienen override en sucursal, esto hace que el sistema tenga
    un mínimo/reorden razonable a heredar.
    """
    n = 0
    for art in articulos:
        if random.random() > 0.50:
            continue
        minimo = random.choice([5, 10, 15])
        reorden = minimo + random.choice([10, 15, 20])
        maximo = reorden + random.choice([50, 80, 100])
        art.stock_minimo_default = Decimal(str(minimo))
        art.punto_reorden_default = Decimal(str(reorden))
        art.stock_maximo_default = Decimal(str(maximo))
        art.lead_time_dias_default = random.choice([5, 7, 10])
        n += 1
    db.session.commit()
    echo(f"articulos defaults stock OK ({n})")
    return n


def _seed_clientes(echo, fake) -> int:
    rows: list[dict[str, Any]] = []

    # Consumidor Final
    if db.session.query(Cliente).filter(Cliente.codigo == "CF").first() is None:
        rows.append(
            {
                "codigo": "CF",
                "razon_social": "Consumidor Final",
                "cuit": None,
                "condicion_iva": CondicionIvaEnum.consumidor_final,
                "cuenta_corriente": False,
                "saldo": Decimal("0"),
                "activo": True,
            }
        )

    # 10 RI
    for i in range(1, 11):
        codigo = f"CLI{i:04d}"
        if db.session.query(Cliente).filter(Cliente.codigo == codigo).first():
            continue
        dni = f"{random.randint(20000000, 49999999)}"
        rows.append(
            {
                "codigo": codigo,
                "razon_social": fake.company(),
                "cuit": _cuit("30", dni),
                "condicion_iva": CondicionIvaEnum.responsable_inscripto,
                "telefono": fake.phone_number()[:50],
                "email": fake.company_email()[:200],
                "direccion": fake.address().replace("\n", " ")[:255],
                "cuenta_corriente": random.random() < 0.4,
                "limite_cuenta_corriente": Decimal(str(random.choice([0, 50000, 100000, 200000]))),
                "saldo": Decimal("0"),
                "activo": True,
            }
        )

    # 15 Monotributistas
    for i in range(11, 26):
        codigo = f"CLI{i:04d}"
        if db.session.query(Cliente).filter(Cliente.codigo == codigo).first():
            continue
        dni = f"{random.randint(20000000, 49999999)}"
        rows.append(
            {
                "codigo": codigo,
                "razon_social": fake.name(),
                "cuit": _cuit("20", dni),
                "condicion_iva": CondicionIvaEnum.monotributo,
                "telefono": fake.phone_number()[:50],
                "email": fake.email()[:200],
                "direccion": fake.address().replace("\n", " ")[:255],
                "cuenta_corriente": random.random() < 0.4,
                "limite_cuenta_corriente": Decimal(str(random.choice([0, 30000, 80000]))),
                "saldo": Decimal("0"),
                "activo": True,
            }
        )

    # 5 Exentos
    for i in range(26, 31):
        codigo = f"CLI{i:04d}"
        if db.session.query(Cliente).filter(Cliente.codigo == codigo).first():
            continue
        dni = f"{random.randint(20000000, 49999999)}"
        rows.append(
            {
                "codigo": codigo,
                "razon_social": fake.company() + " (Exento)",
                "cuit": _cuit("30", dni),
                "condicion_iva": CondicionIvaEnum.exento,
                "telefono": fake.phone_number()[:50],
                "email": fake.company_email()[:200],
                "direccion": fake.address().replace("\n", " ")[:255],
                "cuenta_corriente": False,
                "saldo": Decimal("0"),
                "activo": True,
            }
        )

    if rows:
        db.session.execute(insert(Cliente), rows)
        db.session.commit()
    total = db.session.query(Cliente).count()
    echo(f"clientes OK ({total})")
    return total


def _seed_users(echo, suc_by_code: dict[str, Sucursal]) -> int:
    # Admin ya está; agregamos 4 cajeros + 2 supervisores + 1 contador.
    sucursales = list(suc_by_code.values())
    nuevos = []

    # Cajeros — uno por sucursal
    for i, suc in enumerate(sucursales[:4], start=1):
        email = f"cajero{i}@casasalco.app"
        if db.session.query(User).filter(User.email == email).first():
            continue
        nuevos.append(
            User(
                email=email,
                password_hash=hash_password("cajero123"),
                nombre=f"Cajero {suc.nombre}",
                rol=RolEnum.cajero,
                sucursal_id=suc.id,
                activo=True,
            )
        )
    # Supervisores
    for i in range(1, 3):
        email = f"supervisor{i}@casasalco.app"
        if db.session.query(User).filter(User.email == email).first():
            continue
        nuevos.append(
            User(
                email=email,
                password_hash=hash_password("super123"),
                nombre=f"Supervisor {i}",
                rol=RolEnum.supervisor,
                activo=True,
            )
        )
    # Contador
    if not db.session.query(User).filter(User.email == "contador@casasalco.app").first():
        nuevos.append(
            User(
                email="contador@casasalco.app",
                password_hash=hash_password("contador123"),
                nombre="Contador",
                rol=RolEnum.contador,
                activo=True,
            )
        )

    for u in nuevos:
        db.session.add(u)
    db.session.commit()
    total = db.session.query(User).count()
    echo(f"users OK (total={total}, nuevos={len(nuevos)})")
    return total


# =========================================================
# Historial ventas
# =========================================================


def _fecha_hora_venta(dia: date) -> datetime:
    """Elige una hora dentro del día, pesada hacia horas pico (9-12, 17-20)."""
    # Buckets: madrugada (0-6)=0.01, mañana (7-12)=0.35, tarde (13-16)=0.15,
    # tarde-noche (17-20)=0.40, noche (21-23)=0.09
    hour = random.choices(
        population=list(range(24)),
        weights=[
            0.005, 0.003, 0.002, 0.002, 0.003, 0.010,  # 0-5
            0.020,                                     # 6
            0.050, 0.080, 0.100, 0.110, 0.090,         # 7-11
            0.060, 0.040, 0.040, 0.045,                # 12-15
            0.080, 0.120, 0.100, 0.060,                # 16-19
            0.040, 0.025, 0.010, 0.005,                # 20-23
        ],
    )[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return datetime(dia.year, dia.month, dia.day, hour, minute, second, tzinfo=UTC)


def _peso_dia_semana(dia: date) -> float:
    """Peso relativo por día de la semana (lun=0 ... dom=6)."""
    weekday = dia.weekday()
    # Lun flojo, mié mid, vie-sáb fuerte, dom muy flojo
    weights = [0.90, 1.00, 1.05, 1.05, 1.30, 1.35, 0.15]
    return weights[weekday]


def _pick_sucursal(sucursales_peso: list[tuple[Sucursal, float]]) -> Sucursal:
    sucs, pesos = zip(*sucursales_peso)
    return random.choices(sucs, weights=pesos)[0]


def _pick_tipo_comprobante() -> TipoComprobanteEnum:
    return random.choices(
        [
            TipoComprobanteEnum.ticket,
            TipoComprobanteEnum.factura_b,
            TipoComprobanteEnum.factura_a,
            TipoComprobanteEnum.factura_c,
        ],
        weights=[0.80, 0.12, 0.05, 0.03],
    )[0]


def _pick_medios_pago(total: Decimal) -> list[tuple[MedioPagoEnum, Decimal]]:
    """Devuelve lista de (medio, monto) que suman total."""
    total = _round2(total)
    r = random.random()
    if r < 0.40:
        return [(MedioPagoEnum.efectivo, total)]
    elif r < 0.70:
        medio = random.choice([MedioPagoEnum.tarjeta_debito, MedioPagoEnum.tarjeta_credito])
        return [(medio, total)]
    elif r < 0.85:
        return [(random.choice([MedioPagoEnum.qr_mercadopago, MedioPagoEnum.qr_modo]), total)]
    elif r < 0.95:
        # Split efectivo + tarjeta
        efe_pct = Decimal(str(random.uniform(0.30, 0.70)))
        efe = _round2(total * efe_pct)
        tar = _round2(total - efe)
        return [
            (MedioPagoEnum.efectivo, efe),
            (random.choice([MedioPagoEnum.tarjeta_debito, MedioPagoEnum.tarjeta_credito]), tar),
        ]
    else:
        return [(MedioPagoEnum.cuenta_corriente, total)]


def _calc_linea(
    cantidad: Decimal, precio: Decimal, iva_porc: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = _round4(cantidad * precio)
    iva_monto = _round4(subtotal * (iva_porc / Decimal("100")))
    total = _round4(subtotal + iva_monto)
    return subtotal, iva_monto, total


def _seed_historial_ventas(
    echo,
    articulos: list[Articulo],
    suc_by_code: dict[str, Sucursal],
    fake,
) -> tuple[int, int, int, int, int]:
    """Crea 300-600 facturas en los últimos 30 días con patrones reales.

    Retorna: (n_facturas, n_items, n_pagos, n_movs, n_caes)
    """
    # Cajeros por sucursal
    cajeros_by_suc: dict[int, int] = {}  # sucursal_id -> user_id
    for suc in suc_by_code.values():
        cajero = (
            db.session.query(User)
            .filter(User.rol == RolEnum.cajero, User.sucursal_id == suc.id)
            .first()
        )
        if cajero:
            cajeros_by_suc[suc.id] = cajero.id
        else:
            admin = db.session.query(User).filter(User.rol == RolEnum.admin).first()
            cajeros_by_suc[suc.id] = admin.id if admin else 1

    # Sucursales con peso
    sucursales_peso = [
        (suc_by_code[d["codigo"]], d["peso"]) for d in _SUCURSALES
    ]

    # Clientes ctacte (para el 5% de ventas ctacte)
    clientes_ctacte = (
        db.session.query(Cliente)
        .filter(Cliente.cuenta_corriente.is_(True), Cliente.activo.is_(True))
        .all()
    )
    clientes_ri = (
        db.session.query(Cliente)
        .filter(Cliente.condicion_iva == CondicionIvaEnum.responsable_inscripto)
        .all()
    )

    # Artículos populares (~20% del catálogo) — reciben más ventas
    articulos_activos = [a for a in articulos if a.activo]
    populares_n = max(1, int(len(articulos_activos) * 0.20))
    # Favorecer ciertas familias (pan, lacteos, bebidas)
    fam_pop = {"LAC", "PAN", "BSA", "ALM"}
    candidatos_populares = [a for a in articulos_activos if _familia_codigo(a) in fam_pop]
    if len(candidatos_populares) < populares_n:
        candidatos_populares = articulos_activos
    populares = random.sample(candidatos_populares, min(populares_n, len(candidatos_populares)))
    populares_ids = {a.id for a in populares}

    # Stock cache (articulo_id, sucursal_id) -> cantidad disponible
    stock_cache: dict[tuple[int, int], Decimal] = {}
    for row in db.session.query(StockSucursal).all():
        stock_cache[(row.articulo_id, row.sucursal_id)] = row.cantidad

    # Articulo por id
    art_by_id: dict[int, Articulo] = {a.id: a for a in articulos_activos}
    art_ids_all = list(art_by_id.keys())
    art_ids_populares = [aid for aid in populares_ids if aid in art_by_id]

    # Precio por (articulo, sucursal)
    precios_cache: dict[tuple[int, int], Decimal] = {}
    for row in db.session.query(PrecioSucursal).filter(PrecioSucursal.activo.is_(True)).all():
        precios_cache[(row.articulo_id, row.sucursal_id)] = row.precio

    # Número inicial por (suc_id, pv, tipo)
    numero_counter: dict[tuple[int, int, TipoComprobanteEnum], int] = {}

    # Total objetivo de facturas — generamos por día con peso
    target_total = random.randint(320, 560)
    dias = [date.today() - timedelta(days=i) for i in range(30)]
    pesos_dias = [_peso_dia_semana(d) for d in dias]
    suma_peso = sum(pesos_dias)
    facturas_por_dia = [
        max(1, int(round(target_total * p / suma_peso))) for p in pesos_dias
    ]

    # Para AFIP mock
    from app.services.afip import get_provider
    try:
        provider = get_provider()
        caes_enabled = True
    except Exception:
        provider = None
        caes_enabled = False

    TIPO_AFIP = {
        TipoComprobanteEnum.factura_a: 1,
        TipoComprobanteEnum.factura_b: 6,
        TipoComprobanteEnum.factura_c: 11,
    }

    # Acumuladores
    fact_rows: list[dict[str, Any]] = []
    item_rows_by_factura: list[tuple[int, list[dict[str, Any]]]] = []  # pendientes de asignar factura_id
    pago_rows_by_factura: list[tuple[int, list[dict[str, Any]]]] = []
    mov_rows_by_factura: list[tuple[int, list[dict[str, Any]]]] = []
    cae_rows_by_factura: list[tuple[int, dict[str, Any]]] = []

    # Vamos a hacerlo en un approach: crear factura (flush para conseguir id),
    # luego crear items/pagos/movs. Evitamos colisionar con UniqueConstraint.
    n_facturas = 0
    n_items = 0
    n_pagos = 0
    n_movs = 0
    n_caes = 0

    total_a_crear = sum(facturas_por_dia)
    with click.progressbar(length=total_a_crear, label="Ventas 30d") as bar:
        for d_idx, dia in enumerate(dias):
            cuantas = facturas_por_dia[d_idx]
            for _ in range(cuantas):
                bar.update(1)
                try:
                    suc = _pick_sucursal(sucursales_peso)
                    tipo = _pick_tipo_comprobante()
                    punto_venta = 1
                    key_num = (suc.id, punto_venta, tipo)
                    numero_counter[key_num] = numero_counter.get(key_num, 0) + 1
                    numero = numero_counter[key_num]
                    fecha = _fecha_hora_venta(dia)

                    # Items: distribución log-normal, mayoría 3-8
                    # Usamos lognormvariate
                    n_items_factura = max(1, min(25, int(random.lognormvariate(1.5, 0.6))))

                    items_calc: list[dict[str, Any]] = []
                    subtotal_fact = Decimal("0")
                    iva_fact = Decimal("0")
                    total_fact = Decimal("0")
                    intentos = 0
                    seen_art_ids: set[int] = set()
                    while len(items_calc) < n_items_factura and intentos < n_items_factura * 4:
                        intentos += 1
                        # 30% eligen popular, 70% random
                        if art_ids_populares and random.random() < 0.30:
                            aid = random.choice(art_ids_populares)
                        else:
                            aid = random.choice(art_ids_all)
                        if aid in seen_art_ids:
                            continue
                        art = art_by_id.get(aid)
                        if art is None:
                            continue
                        # Stock disponible en la sucursal
                        disp = stock_cache.get((aid, suc.id), Decimal("0"))
                        if disp <= Decimal("0"):
                            continue
                        # Cantidad: 1-3 mayormente, algunos mayores para kg
                        if art.unidad_medida == UnidadMedidaEnum.kg:
                            cantidad = _round4(Decimal(str(random.uniform(0.1, 2.0))))
                        else:
                            cantidad = Decimal(str(random.choices(
                                [1, 2, 3, 4, 6], weights=[0.55, 0.25, 0.12, 0.05, 0.03]
                            )[0]))
                        if disp < cantidad:
                            # Ajustamos al stock disponible si es razonable
                            if disp >= Decimal("1"):
                                cantidad = disp.quantize(Q4, rounding=ROUND_HALF_UP)
                            else:
                                continue
                        precio = precios_cache.get((aid, suc.id), art.pvp_base)
                        iva_porc = art.iva_porc
                        subtotal, iva_monto, total_l = _calc_linea(cantidad, precio, iva_porc)
                        items_calc.append(
                            {
                                "articulo_id": aid,
                                "articulo": art,
                                "codigo": art.codigo,
                                "descripcion": art.descripcion,
                                "cantidad": cantidad,
                                "precio_unitario": _round4(precio),
                                "descuento_porc": Decimal("0"),
                                "iva_porc": iva_porc,
                                "iva_monto": iva_monto,
                                "subtotal": subtotal,
                                "total": total_l,
                            }
                        )
                        seen_art_ids.add(aid)
                        subtotal_fact += subtotal
                        iva_fact += iva_monto
                        total_fact += total_l

                    if not items_calc:
                        # No se pudo armar la venta — skip este
                        numero_counter[key_num] -= 1
                        continue

                    subtotal_fact = _round2(subtotal_fact)
                    iva_fact = _round2(iva_fact)
                    total_fact = _round2(total_fact)

                    # Medios de pago
                    medios = _pick_medios_pago(total_fact)
                    # Si incluye ctacte pero no hay clientes ctacte, pasar a efectivo
                    usa_ctacte = any(m == MedioPagoEnum.cuenta_corriente for m, _ in medios)
                    cliente_id: int | None = None
                    if usa_ctacte:
                        if clientes_ctacte:
                            cliente_id = random.choice(clientes_ctacte).id
                        else:
                            medios = [(MedioPagoEnum.efectivo, total_fact)]

                    # Para facturas A, buscar cliente RI
                    if tipo == TipoComprobanteEnum.factura_a:
                        if clientes_ri:
                            cliente_id = random.choice(clientes_ri).id

                    cajero_id = cajeros_by_suc[suc.id]

                    factura = Factura(
                        sucursal_id=suc.id,
                        punto_venta=punto_venta,
                        tipo=tipo,
                        numero=numero,
                        fecha=fecha,
                        cliente_id=cliente_id,
                        cajero_id=cajero_id,
                        estado=EstadoComprobanteEnum.emitida,
                        subtotal=subtotal_fact,
                        total_iva=iva_fact,
                        total_descuento=Decimal("0"),
                        total=total_fact,
                        moneda="ARS",
                        cotizacion=Decimal("1"),
                    )
                    db.session.add(factura)
                    db.session.flush()

                    for idx, calc in enumerate(items_calc):
                        db.session.add(
                            FacturaItem(
                                factura_id=factura.id,
                                articulo_id=calc["articulo_id"],
                                codigo=calc["codigo"],
                                descripcion=calc["descripcion"],
                                cantidad=calc["cantidad"],
                                precio_unitario=calc["precio_unitario"],
                                descuento_porc=calc["descuento_porc"],
                                iva_porc=calc["iva_porc"],
                                iva_monto=calc["iva_monto"],
                                subtotal=calc["subtotal"],
                                total=calc["total"],
                                orden=idx,
                            )
                        )
                        # Decrementar stock cache
                        key_stock = (calc["articulo_id"], suc.id)
                        stock_cache[key_stock] = stock_cache.get(key_stock, Decimal("0")) - calc["cantidad"]
                        n_items += 1

                    for pidx, (medio, monto) in enumerate(medios):
                        db.session.add(
                            FacturaPago(
                                factura_id=factura.id,
                                medio=medio,
                                monto=_round2(monto),
                                orden=pidx,
                            )
                        )
                        n_pagos += 1
                        db.session.add(
                            MovimientoCaja(
                                sucursal_id=suc.id,
                                caja_numero=1,
                                fecha_caja=fecha.date(),
                                fecha=fecha,
                                tipo=TipoMovimientoEnum.venta,
                                medio=medio,
                                monto=_round2(monto),
                                factura_id=factura.id,
                                cliente_id=cliente_id,
                                descripcion=(
                                    f"Venta {tipo.value} "
                                    f"{punto_venta:04d}-{numero:08d}"
                                ),
                                user_id=cajero_id,
                            )
                        )
                        n_movs += 1

                    # CAE mock para A/B/C
                    if caes_enabled and tipo in TIPO_AFIP and provider is not None:
                        try:
                            from app.services.afip.base import AfipFacturaInput

                            cli_doc = "0"
                            cli_doc_tipo = 99  # Consumidor final por defecto
                            cond_iva_rec = 5  # Consumidor Final (RG 5616)
                            if cliente_id:
                                cli = db.session.get(Cliente, cliente_id)
                                if cli and cli.cuit:
                                    cli_doc = cli.cuit.replace("-", "")
                                    cli_doc_tipo = 80
                                    if cli.condicion_iva == CondicionIvaEnum.responsable_inscripto:
                                        cond_iva_rec = 1
                                    elif cli.condicion_iva == CondicionIvaEnum.monotributo:
                                        cond_iva_rec = 6
                                    elif cli.condicion_iva == CondicionIvaEnum.exento:
                                        cond_iva_rec = 4

                            inp = AfipFacturaInput(
                                cuit_emisor="20000000001",
                                tipo_afip=TIPO_AFIP[tipo],
                                punto_venta=punto_venta,
                                concepto=1,
                                tipo_doc_receptor=cli_doc_tipo,
                                nro_doc_receptor=cli_doc,
                                cond_iva_receptor_id=cond_iva_rec,
                                fecha_comprobante=fecha.date(),
                                importe_neto=subtotal_fact,
                                importe_iva=iva_fact,
                                importe_total=total_fact,
                                moneda="PES",
                                cotizacion=Decimal("1"),
                            )
                            out = provider.solicitar_cae(inp)
                            factura.cae = out.cae
                            factura.cae_vencimiento = out.fecha_vencimiento
                            db.session.add(
                                Cae(
                                    factura_id=factura.id,
                                    cuit_emisor="20000000001",
                                    tipo_afip=TIPO_AFIP[tipo],
                                    punto_venta=punto_venta,
                                    numero=numero,
                                    cae=out.cae,
                                    fecha_vencimiento=out.fecha_vencimiento,
                                    fecha_emision=fecha,
                                    proveedor="mock",
                                    response_xml=out.response_xml,
                                    qr_url="",
                                    resultado=out.resultado,
                                    reproceso=out.reproceso,
                                )
                            )
                            n_caes += 1
                        except Exception:
                            # CAE es best-effort; si falla, seguimos
                            pass

                    n_facturas += 1

                    # Commit cada 25 facturas para no acumular memoria
                    if n_facturas % 25 == 0:
                        db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    click.echo(f"  error en factura (skip): {exc}", err=True)
                    continue

    db.session.commit()

    # Persistir stock modificado
    # (ya lo modificamos en memoria — hay que bajar a DB)
    _flush_stock_cache(stock_cache)

    echo(
        f"ventas 30d OK "
        f"(facturas={n_facturas} items={n_items} pagos={n_pagos} "
        f"movs={n_movs} caes={n_caes})"
    )
    return n_facturas, n_items, n_pagos, n_movs, n_caes


def _flush_stock_cache(stock_cache: dict[tuple[int, int], Decimal]) -> None:
    """Persiste los cambios del stock_cache a la DB (batch update)."""
    # Hacemos UPDATE en bulk con un dict per row
    for (art_id, suc_id), qty in stock_cache.items():
        row = (
            db.session.query(StockSucursal)
            .filter(
                StockSucursal.articulo_id == art_id,
                StockSucursal.sucursal_id == suc_id,
            )
            .first()
        )
        if row is None:
            db.session.add(
                StockSucursal(
                    articulo_id=art_id,
                    sucursal_id=suc_id,
                    cantidad=qty if qty >= Decimal("0") else Decimal("0"),
                )
            )
        else:
            row.cantidad = qty if qty >= Decimal("0") else Decimal("0")
    db.session.commit()


def _familia_codigo(art: Articulo) -> str:
    """Helper: devuelve el código de familia del artículo (parseando su código)."""
    if not art.codigo or "-" not in art.codigo:
        return ""
    return art.codigo.split("-", 1)[0]
