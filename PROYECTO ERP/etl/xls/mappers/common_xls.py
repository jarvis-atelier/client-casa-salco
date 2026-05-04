"""Helpers comunes para mappers de archivos .xls (BIFF legacy).

- `decode_xls_str`: aplicado en READ-time, idempotente, repara mojibake cp1252
  producido por xlrd 1.2.0 al leer archivos BIFF legacy.
- `read_sheet`: generator que itera filas de una sheet como dicts (header → valor),
  decodificando strings con `decode_xls_str` antes de yieldear.
- `flush_every`: helper de batching para flushear la session ORM cada N filas.

Patron paralelo a `etl/mappers/common.py` (DBF importer): no duplicar logica
generica como `clean_str`, `sanitize_text`, `decimal_or_zero` o `LoadReport` —
esos viven en `etl.mappers.common` y deben reusarse desde alli.
"""
from __future__ import annotations

from typing import Any, Iterator

import xlrd


def decode_xls_str(s: Any) -> Any:
    """Repara mojibake cp1252 en strings leidos por xlrd 1.2.0 desde BIFF .xls.

    xlrd 1.2.0 decodifica las celdas string de BIFF como si fueran latin-1,
    pero los archivos legacy de Casa Salco fueron escritos en cp1252. Eso
    produce mojibake del tipo `"C\\xf3digo"` en lugar de `"Código"`.

    Solucion: reencodear a latin-1 (1:1, byte-perfect) y volver a decodear
    como cp1252. Idempotente sobre strings ya limpios (utf-8 sin acentos
    perdidos): el roundtrip latin-1/cp1252 los devuelve igual.

    Pasthrough seguro para None, int, float y otros no-strings.
    """
    if s is None:
        return None
    if not isinstance(s, str):
        return s
    try:
        return s.encode('latin-1', 'replace').decode('cp1252', 'replace')
    except (UnicodeError, ValueError):
        return s


def read_sheet(workbook_path: str, sheet_name: str) -> Iterator[dict]:
    """Itera filas de una sheet BIFF .xls como dicts.

    La fila 0 se trata como header y provee los nombres de columna. Todas
    las celdas string son decodificadas via `decode_xls_str` ANTES de
    yieldear. Las celdas numericas (int / float) pasan sin tocar.

    Usa `xlrd.open_workbook(on_demand=True)` para lazy-load por sheet y
    libera recursos en el `finally` para mantener el footprint de memoria
    acotado al iterar archivos de ~50k filas.
    """
    book = xlrd.open_workbook(workbook_path, on_demand=True, formatting_info=False)
    try:
        sheet = book.sheet_by_name(sheet_name)
        rows_iter = sheet.get_rows()
        try:
            header = [decode_xls_str(c.value) for c in next(rows_iter)]
        except StopIteration:
            return
        for raw_row in rows_iter:
            yield {
                header[i]: (decode_xls_str(c.value) if isinstance(c.value, str) else c.value)
                for i, c in enumerate(raw_row)
                if i < len(header)
            }
    finally:
        book.release_resources()


def flush_every(session, items: list, n: int = 1000) -> None:
    """Agrega `items` a la session y hace flush si hay algo que flushear.

    El caller es responsable de limpiar `items` despues del flush. Uso
    idiomatico:

        batch = []
        for row in rows:
            batch.append(MyModel(...))
            if len(batch) >= 1000:
                flush_every(session, batch, 1000)
                batch.clear()
        if batch:
            flush_every(session, batch, 1000)
            batch.clear()

    No existe helper equivalente en `etl/mappers/common.py` — los mappers
    DBF llaman a `session.flush()` inline. Centralizar aca para que los
    mappers .xls (3 entidades) compartan el mismo patron sin repetir
    el codigo de batching.
    """
    if items:
        session.add_all(items)
        session.flush()
