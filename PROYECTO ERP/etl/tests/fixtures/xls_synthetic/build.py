"""Build the 3 synthetic .xls fixtures used by the xls importer integration tests.

Runs deterministically: each row is hand-curated to exercise a specific code
path (junk filter, mojibake decode, FK fallback, intra-sheet duplicate, etc.).

Usage (manual; NOT part of CI):

    cd "PROYECTO ERP"
    ./backend/.venv/Scripts/python.exe etl/tests/fixtures/xls_synthetic/build.py

Output files (committed alongside this script):

- proveedores.xls               — sheet `proveedor` (5 rows)
- articulos.xls                 — sheet `Sheet1` (10 rows)
- articulos_proveedores.xls     — sheet `RELACION PRODUCTOS PROVEEDOR` (5 rows)

## Encoding round-trip

The real Casa Salco .xls files have cp1252-encoded byte cells. xlrd 1.2.0
reads those cells as latin-1 (which is byte-identical to cp1252 in the
0xA0-0xFF range), so cells like "Codigo" with byte 0xF3 for o-acute
surface as Python codepoint U+00F3 = o-acute. `decode_xls_str` is then
applied; for these chars it's effectively a no-op (idempotent), but it
ALSO repairs the actual mojibake cases where xlrd surfaces 0x80-0x9F
control chars (cp1252-specific high bytes that latin-1 doesn't have).

These fixtures use the simple case: literal Python strings like
"Espa\\xf1a" (where \\xf1 is U+00F1 = small n-tilde). xlwt encodes
this as cp1252 byte 0xF1; xlrd reads it back as U+00F1; decode_xls_str
roundtrips it through latin-1 -> cp1252 unchanged. Test matrix in the
spec is therefore an idempotence test, not a repair test.

## Header conventions

`articulos_proveedores.xls` mirrors the trailing-space header convention
found in real File 1 (`'nombre del proveedor '`, `'cantidad '`). The
mappers `etl/xls/mappers/articulos_proveedores_xls.py` look up these
keys with the trailing space preserved.
"""
from __future__ import annotations

from pathlib import Path

import xlwt

FIXTURES_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Sheet 1 — proveedores.xls
# ---------------------------------------------------------------------------
#
# Headers mirror those in `etl/xls/mappers/proveedores_xls.py`:
#   Codigo | Nombre | Telefono | Email | Clasificacion |
#   Descripcion clasificacion proveedor | CUIT
#
# In the real file these come back from xlrd as mojibake (`C\xf3digo`),
# so we write the literal mojibake form here so `decode_xls_str` round-trips
# correctly.
PROVEEDORES_HEADERS = [
    "C\xf3digo",                                  # -> "Código" (idempotent)
    "Nombre",
    "Tel\xe9fono",                                # -> "Teléfono"
    "Email",
    "Clasificaci\xf3n",                           # -> "Clasificación"
    "Descripci\xf3n clasificaci\xf3n proveedor",  # -> "Descripción clasificación proveedor"
    "CUIT",
]

PROVEEDORES_ROWS = [
    # (codigo, nombre, telefono, email, clasif, desc_clasif, cuit)

    # 1) Normal proveedor.
    ("P001", "Acme SA", "0341-1234567", "test@example.com", "A", "Activo", "20-12345678-9"),

    # 2) Latin-1 high-byte row — `nombre` contains n-tilde (\xf1).
    #    After decode_xls_str, persisted razon_social MUST be "España SA".
    ("P002", "Espa\xf1a SA", "0341-7654321", "espana@example.com", "B", "Mayorista", "30-11223344-5"),

    # 3) Junk: codigo == '0000'. Must be filtered.
    ("0000", "ZZZ JUNK", "", "", "", "", ""),

    # 4) Junk: codigo == nombre (legacy garbage). Must be filtered.
    ("BASURA", "BASURA", "", "", "", "", ""),

    # 5) Normal proveedor with everything populated (used by S1 happy path).
    ("P003", "Distribuidora Sur", "011-5550000", "sur@example.com", "C", "Frecuente", "27-99887766-1"),
]


# ---------------------------------------------------------------------------
# Sheet 2 — articulos.xls
# ---------------------------------------------------------------------------
#
# Headers verified against `etl/xls/mappers/articulos_xls.py`:
#   Articulo | Descripcion | Unidad de medida | Proveedor | NOMBRE PROVEEDOR |
#   COMPRA | PUBLICO | RUBRO | Grupo | MARCA | Marca NOMBRE | GRUPDESC | CATEGORIA
ARTICULOS_HEADERS = [
    "Art\xedculo",     # -> "Artículo"
    "Descripci\xf3n",  # -> "Descripción"
    "Unidad de medida",
    "Proveedor",
    "NOMBRE PROVEEDOR",
    "COMPRA",
    "PUBLICO",
    "RUBRO",
    "Grupo",
    "MARCA",
    "Marca NOMBRE",
    "GRUPDESC",
    "CATEGORIA",
]

ARTICULOS_ROWS = [
    # (codigo, descripcion, unidad, prov_codigo, prov_nombre, compra, publico,
    #  rubro, grupo, marca, marca_nombre, grupdesc, categoria)

    # 1) Normal articulo with valid proveedor FK + valid raw catalog values.
    #    rubro/familia don't exist in test taxonomy so they fall back to sin-*.
    ("ART01", "Aceite Cocinero", "LT", "P001", "Acme SA", 100.50, 150.75,
     "ALMACEN-CONDIMENTOS", "ALMACEN", "COCINERO", "Cocinero", "ACEITES", "BASICOS"),

    # 2) compra=0 — for skip-compra-cero flag tests (default OFF imports it).
    ("ART02", "Producto Compra Cero", "UN", "P001", "Acme SA", 0.0, 100.0,
     "VARIOS", "VARIOS", "GENERICO", "", "", ""),

    # 3) Unknown proveedor codigo (XX999). FK miss -> proveedor_principal_id=NULL + WARN.
    ("ART03", "Producto Sin Proveedor", "KG", "XX999", "Inexistente", 50.0, 75.0,
     "ALMACEN", "ALMACEN", "MARCA-X", "", "", ""),

    # 4) Junk: codigo == '0000'. Must be filtered.
    ("0000", "junk row", "UN", "P001", "Acme SA", 1.0, 2.0,
     "", "", "", "", "", ""),

    # 5) Latin-1 high-byte descripcion - small n-tilde (0xf1).
    ("ART05", "Galletitas ñandutiloka", "UN", "P003", "Distribuidora Sur", 25.0, 40.0,
     "GALLETITAS", "DULCES", "GENERICA", "", "", ""),

    # 6) unidad="K" (1-char) — legacy single-char form.
    ("ART06", "Yerba en Kilos", "K", "P003", "Distribuidora Sur", 200.0, 300.0,
     "YERBAS", "INFUSIONES", "PLAYADITO", "", "", ""),

    # 7) unidad="KG" (2-char) — alternate form for same enum value.
    ("ART07", "Azucar Refinada", "KG", "P003", "Distribuidora Sur", 80.0, 110.0,
     "ENDULZANTES", "ALMACEN", "LEDESMA", "", "", ""),

    # 8) Duplicate of ART01 with DIFFERENT descripcion — last-wins test.
    ("ART01", "Aceite Cocinero MODIFIED", "LT", "P001", "Acme SA", 105.0, 160.0,
     "ALMACEN-CONDIMENTOS", "ALMACEN", "COCINERO", "", "", ""),

    # 9) Articulo "ART09" — used by ArticuloProveedor pair tests.
    ("ART09", "Pan Lactal", "UN", "P001", "Acme SA", 12.0, 20.0,
     "PANIFICADOS", "PANADERIA", "BIMBO", "", "", ""),

    # 10) Articulo "ART10" — used by ArticuloProveedor pair tests.
    ("ART10", "Leche Entera", "LT", "P003", "Distribuidora Sur", 18.0, 28.0,
     "LACTEOS", "LACTEOS", "LASERENISIMA", "", "", ""),
]


# ---------------------------------------------------------------------------
# Sheet 3 — articulos_proveedores.xls
# ---------------------------------------------------------------------------
#
# Real File 1 has trailing-space header convention (`'nombre del proveedor '`,
# `'cantidad '`). Verified against `etl/xls/mappers/articulos_proveedores_xls.py`.
ARTPROV_HEADERS = [
    "codigo articulo",
    "codigo proveedor",
    "nombre del proveedor ",                      # trailing space
    "codigo del producto x el proveedor",
    "cantidad ",                                  # trailing space; DROPPED per Decision 6
]

ARTPROV_ROWS = [
    # (cod_articulo, cod_proveedor, nombre_proveedor, codigo_alterno, cantidad)

    # 1) Normal pair: ART09 + P001
    ("ART09", "P001", "Acme SA", "PROV-CODE-1", 1),

    # 2) Normal pair: ART10 + P003
    ("ART10", "P003", "Distribuidora Sur", "PROV-CODE-2", 1),

    # 3) Missing proveedor FK (XX999) -> SKIP + WARN
    ("ART09", "XX999", "Inexistente", "PROV-CODE-3", 1),

    # 4) Missing articulo FK (NOEXISTE) -> SKIP + WARN
    ("NOEXISTE", "P001", "Acme SA", "PROV-CODE-4", 1),

    # 5) Row with cantidad=5 — must be DROPPED per Decision 6
    #    (no field on ArticuloProveedor model). Pair itself is normal.
    ("ART01", "P001", "Acme SA", "PROV-CODE-5", 5),
]


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _write_sheet(book: xlwt.Workbook, sheet_name: str, headers: list,
                 rows: list[tuple]) -> None:
    sh = book.add_sheet(sheet_name, cell_overwrite_ok=True)
    for col_idx, h in enumerate(headers):
        sh.write(0, col_idx, h)
    for row_idx, row in enumerate(rows, start=1):
        for col_idx, value in enumerate(row):
            if value is None or value == "":
                # leave the cell empty (xlrd reads it back as empty string).
                continue
            sh.write(row_idx, col_idx, value)


def build_proveedores(out_path: Path) -> None:
    book = xlwt.Workbook(encoding="cp1252")
    _write_sheet(book, "proveedor", PROVEEDORES_HEADERS, PROVEEDORES_ROWS)
    book.save(str(out_path))


def build_articulos(out_path: Path) -> None:
    book = xlwt.Workbook(encoding="cp1252")
    _write_sheet(book, "Sheet1", ARTICULOS_HEADERS, ARTICULOS_ROWS)
    book.save(str(out_path))


def build_articulos_proveedores(out_path: Path) -> None:
    book = xlwt.Workbook(encoding="cp1252")
    _write_sheet(
        book,
        "RELACION PRODUCTOS PROVEEDOR",
        ARTPROV_HEADERS,
        ARTPROV_ROWS,
    )
    book.save(str(out_path))


def build_all(out_dir: Path = FIXTURES_DIR) -> dict:
    """Build all 3 fixtures and return their paths.

    Returns a dict for use by tests/CI:
        {"proveedores": Path, "articulos": Path, "articulos_proveedores": Path}
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "proveedores": out_dir / "proveedores.xls",
        "articulos": out_dir / "articulos.xls",
        "articulos_proveedores": out_dir / "articulos_proveedores.xls",
    }
    build_proveedores(paths["proveedores"])
    build_articulos(paths["articulos"])
    build_articulos_proveedores(paths["articulos_proveedores"])
    return paths


if __name__ == "__main__":
    paths = build_all()
    for name, path in paths.items():
        size = path.stat().st_size
        print(f"  {name:30s} {path.name:40s} {size:>6} bytes")
    print(f"\nWrote 3 fixtures to {FIXTURES_DIR}")
