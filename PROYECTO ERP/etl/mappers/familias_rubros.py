"""Mapper para la jerarquia Familia -> Rubro desde LINEA.DBF y RUBRO.DBF.

Decisiones de modelado:
  - Legacy NO tiene familia real: RUBRO.DBF son categorias de primer nivel y
    LINEA.DBF es una clasificacion comercial paralela (no jerarquica).
  - El modelo nuevo espera Familia > Rubro > Subrubro. Como no hay padre
    real para los rubros, creamos una familia "General" que cuelga todo.
  - Si LINEA.DBF tiene datos utiles (descripciones distintas de placeholders
    genericos "RUBRO  0"), se migran como familias reales; sino se descartan.
  - Siempre creamos una familia fallback "sin-familia" / rubro fallback
    "sin-rubro" para articulos huerfanos.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from dbfread import DBF

from app.models import Familia, Rubro

from .common import LoadReport, sanitize_text

LINEA_DBF = "LINEA.DBF"
LIN_DBF = "LIN.DBF"
RUBRO_DBF = "RUBRO.DBF"

# Codigos de fallback que creamos siempre
FAMILIA_GENERAL_CODE = "general"
FAMILIA_SIN_CODE = "sin-familia"
RUBRO_SIN_CODE = "sin-rubro"
FAMILIA_GENERAL_NOMBRE = "General"
FAMILIA_SIN_NOMBRE = "Sin familia"
RUBRO_SIN_NOMBRE = "Sin rubro"


@dataclass
class CategoryPlan:
    """Plan de categorias a crear: familias + rubros con FK resuelta logicamente."""

    familias: list[dict]
    rubros: list[dict]  # cada dict incluye "familia_codigo" para resolver FK en load


def _is_placeholder_desc(desc: str | None) -> bool:
    """True si el desc parece placeholder generico (ej. 'RUBRO  0', 'LINEA 3')."""
    if not desc:
        return True
    normalized = desc.strip().upper()
    if normalized.startswith(("RUBRO ", "LINEA ", "LIN ")):
        parts = normalized.split()
        if len(parts) == 2 and parts[1].isdigit():
            return True
    return False


def extract(source_dir: Path, encoding: str = "cp1252") -> Iterator[dict]:
    """No se usa directamente - load() consume el plan construido en plan()."""
    return iter(())


def plan(source_dir: Path, encoding: str = "cp1252") -> CategoryPlan:
    """Construye el plan de Familia/Rubro desde los DBFs disponibles."""
    familias: list[dict] = []
    rubros: list[dict] = []
    seen_familia_codes: set[str] = set()

    # Fallbacks obligatorios
    familias.append({
        "codigo": FAMILIA_GENERAL_CODE,
        "nombre": FAMILIA_GENERAL_NOMBRE,
        "orden": 0,
    })
    familias.append({
        "codigo": FAMILIA_SIN_CODE,
        "nombre": FAMILIA_SIN_NOMBRE,
        "orden": 999,
    })
    seen_familia_codes.update({FAMILIA_GENERAL_CODE, FAMILIA_SIN_CODE})

    # Intentar LINEA.DBF primero, fallback a LIN.DBF si tiene datos reales
    familia_source = None
    for candidate in (LINEA_DBF, LIN_DBF):
        path = source_dir / candidate
        if not path.exists():
            continue
        table = DBF(
            str(path),
            encoding=encoding,
            char_decode_errors="replace",
            ignore_missing_memofile=True,
            lowernames=True,
        )
        has_real = any(
            not _is_placeholder_desc(sanitize_text(r.get("desc")))
            for r in table
            if r.get("codigo") is not None
        )
        if has_real:
            familia_source = candidate
            break

    if familia_source:
        path = source_dir / familia_source
        table = DBF(
            str(path),
            encoding=encoding,
            char_decode_errors="replace",
            ignore_missing_memofile=True,
            lowernames=True,
        )
        for rec in table:
            codigo = rec.get("codigo")
            desc = sanitize_text(rec.get("desc"), max_len=100)
            if codigo is None:
                continue
            if _is_placeholder_desc(desc):
                continue
            codigo_str = f"fam-{int(codigo)}"
            if codigo_str in seen_familia_codes:
                continue
            familias.append({
                "codigo": codigo_str,
                "nombre": desc or f"Familia {codigo}",
                "orden": int(codigo) if isinstance(codigo, (int, float)) else 0,
            })
            seen_familia_codes.add(codigo_str)

    # RUBRO.DBF: cuelga todo de "general", mas un rubro fallback en "sin-familia"
    path = source_dir / RUBRO_DBF
    if path.exists():
        table = DBF(
            str(path),
            encoding=encoding,
            char_decode_errors="replace",
            ignore_missing_memofile=True,
            lowernames=True,
        )
        for rec in table:
            codigo = rec.get("codigo")
            desc = sanitize_text(rec.get("desc"), max_len=100)
            if codigo is None or desc is None:
                continue
            if _is_placeholder_desc(desc):
                continue
            rubros.append({
                "codigo": f"rub-{int(codigo)}",
                "nombre": desc,
                "orden": int(codigo) if isinstance(codigo, (int, float)) else 0,
                "familia_codigo": FAMILIA_GENERAL_CODE,
                "_legacy_code": int(codigo),  # para resolver FK desde ARTICULO.rubro
            })

    # Rubro fallback bajo "sin-familia"
    rubros.append({
        "codigo": RUBRO_SIN_CODE,
        "nombre": RUBRO_SIN_NOMBRE,
        "orden": 999,
        "familia_codigo": FAMILIA_SIN_CODE,
        "_legacy_code": None,
    })

    return CategoryPlan(familias=familias, rubros=rubros)


def load(session, plan_obj: CategoryPlan, *, dry_run: bool = False) -> tuple[LoadReport, LoadReport]:
    """Carga familias y rubros. Devuelve (report_familias, report_rubros)."""
    rep_f = LoadReport(entity="familias")
    rep_f.start()
    rep_r = LoadReport(entity="rubros")
    rep_r.start()

    # Idempotente por codigo
    fam_by_code: dict[str, Familia] = {
        f.codigo: f for f in session.query(Familia).all()
    }

    for row in plan_obj.familias:
        rep_f.read += 1
        codigo = row["codigo"]
        current = fam_by_code.get(codigo)
        if current is None:
            new = Familia(**row)
            if not dry_run:
                session.add(new)
                session.flush()
            fam_by_code[codigo] = new
            rep_f.inserted += 1
        else:
            changed = False
            for key in ("nombre", "orden"):
                if getattr(current, key) != row[key]:
                    if not dry_run:
                        setattr(current, key, row[key])
                    changed = True
            if changed:
                rep_f.updated += 1
            else:
                rep_f.skipped += 1
    rep_f.finish()

    # Rubros: FK por codigo de familia
    # Unicidad de Rubro: (familia_id, codigo) - no codigo solo.
    existing_rubros = session.query(Rubro).all()
    rub_by_key: dict[tuple[int, str], Rubro] = {
        (r.familia_id, r.codigo): r for r in existing_rubros
    }

    for row in plan_obj.rubros:
        rep_r.read += 1
        familia_codigo = row["familia_codigo"]
        familia = fam_by_code.get(familia_codigo)
        if familia is None:
            rep_r.failed += 1
            rep_r.warn(row["codigo"], f"familia '{familia_codigo}' no existe")
            continue
        # En dry_run, familia.id puede ser None si es nueva -> sintetiza key
        fam_id = familia.id if familia.id is not None else -hash(familia_codigo)
        key = (fam_id, row["codigo"])
        current = rub_by_key.get(key)
        if current is None:
            new = Rubro(
                familia=familia,
                codigo=row["codigo"],
                nombre=row["nombre"],
                orden=row["orden"],
            )
            if not dry_run:
                session.add(new)
                session.flush()
            rub_by_key[key] = new
            rep_r.inserted += 1
        else:
            changed = False
            if current.nombre != row["nombre"]:
                if not dry_run:
                    current.nombre = row["nombre"]
                changed = True
            if current.orden != row["orden"]:
                if not dry_run:
                    current.orden = row["orden"]
                changed = True
            if changed:
                rep_r.updated += 1
            else:
                rep_r.skipped += 1
    rep_r.finish()
    return rep_f, rep_r


def build_rubro_lookup(session, plan_obj: CategoryPlan) -> dict[int, Rubro]:
    """Mapa legacy_rubro_code (int) -> instancia Rubro, para uso del mapper articulos."""
    legacy_to_codigo: dict[int, str] = {}
    for row in plan_obj.rubros:
        lc = row.get("_legacy_code")
        if lc is not None:
            legacy_to_codigo[int(lc)] = row["codigo"]

    rubros = session.query(Rubro).all()
    by_codigo = {r.codigo: r for r in rubros}
    return {lc: by_codigo[code] for lc, code in legacy_to_codigo.items() if code in by_codigo}
