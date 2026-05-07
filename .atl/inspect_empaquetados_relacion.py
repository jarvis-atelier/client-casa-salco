"""Read-only inspection of EMPAQUETADOS DE PRODUCTOS + RELACION cantidad column.

For sdd-explore: articulo-multi-codigo-y-presentaciones.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import xlrd  # 1.2.0 in backend/.venv

FILE1 = Path(r"D:\repo\00-omar\CASA SALCO\3EB052EF592E1D591FBB8C-h00ugz.xls")


def decode_xls_str(s):
    """Same helper used by xls importer — re-decode mojibake."""
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin-1", "replace").decode("cp1252", "replace")
    except Exception:
        return s


def main() -> int:
    if not FILE1.exists():
        print(f"NOT FOUND: {FILE1}")
        return 1

    wb = xlrd.open_workbook(str(FILE1), on_demand=True)
    print("=" * 80)
    print(f"FILE: {FILE1.name}")
    print(f"SHEETS: {wb.sheet_names()}")
    print("=" * 80)

    # ============ PHASE 2: EMPAQUETADOS ============
    target = "EMPAQUETADOS DE PRODUCTOS"
    if target not in wb.sheet_names():
        print(f"SHEET MISSING: {target}")
        return 2

    sh = wb.sheet_by_name(target)
    print(f"\n[PHASE 2] Sheet '{target}' shape: rows={sh.nrows}, cols={sh.ncols}")

    headers = [decode_xls_str(sh.cell_value(0, c)) for c in range(sh.ncols)]
    print(f"[PHASE 2] Headers (decoded): {headers}")

    # Dump 12 rows (header + 11 data)
    print("\n[PHASE 2] Sample rows (1..12):")
    for r in range(1, min(13, sh.nrows)):
        row = [decode_xls_str(sh.cell_value(r, c)) for c in range(sh.ncols)]
        print(f"  row {r}: {row}")

    # Stats
    print("\n[PHASE 2] Distribution analysis (full sheet)…")
    codigo_articulo_counter: Counter = Counter()
    codigo_empaq_counter: Counter = Counter()
    cantidad_dist: Counter = Counter()
    null_count_per_col = [0] * sh.ncols
    junk_articulo_codes = 0
    pair_dups: Counter = Counter()
    types_per_col = [Counter() for _ in range(sh.ncols)]

    JUNK_PATTERN_HINTS = ("ASDLAS", "yyyy", "TEST", "PRUEBA", "0088")

    for r in range(1, sh.nrows):
        row = [sh.cell_value(r, c) for c in range(sh.ncols)]
        for c, v in enumerate(row):
            types_per_col[c][type(v).__name__] += 1
            if v in (None, "", 0, 0.0):
                null_count_per_col[c] += 1

        cod_art = row[0]
        cod_emp = row[1] if sh.ncols > 1 else None
        cant = row[2] if sh.ncols > 2 else None

        codigo_articulo_counter[str(cod_art)] += 1
        codigo_empaq_counter[str(cod_emp)] += 1

        # cantidad distribution
        if isinstance(cant, (int, float)):
            cantidad_dist[float(cant)] += 1
        elif isinstance(cant, str):
            cantidad_dist[f"<str:{cant!r}>"] += 1
        else:
            cantidad_dist[f"<{type(cant).__name__}>"] += 1

        # junk detection
        cod_art_s = str(cod_art).upper() if cod_art else ""
        if any(p in cod_art_s for p in JUNK_PATTERN_HINTS):
            junk_articulo_codes += 1

        # pair duplicates (articulo, empaquetado)
        pair_dups[(str(cod_art), str(cod_emp))] += 1

    print(f"  null/empty per col: {null_count_per_col}")
    print(f"  cell types per col: {[dict(t) for t in types_per_col]}")
    print(
        f"  distinct codigo_articulo: {len(codigo_articulo_counter)} "
        f"(top 5: {codigo_articulo_counter.most_common(5)})"
    )
    print(
        f"  distinct codigo_empaquetado: {len(codigo_empaq_counter)} "
        f"(top 5: {codigo_empaq_counter.most_common(5)})"
    )
    print(f"  junk-code rows (heuristic): {junk_articulo_codes}")
    dup_pairs = sum(1 for k, v in pair_dups.items() if v > 1)
    dup_extra_rows = sum(v - 1 for v in pair_dups.values() if v > 1)
    print(
        f"  pair (articulo,empaquetado) duplicates: {dup_pairs} pairs / "
        f"{dup_extra_rows} extra rows"
    )
    print("\n  cantidad distribution (top 20):")
    for k, v in sorted(cantidad_dist.items(), key=lambda kv: -kv[1])[:20]:
        print(f"    {k!r:<30} count={v}")

    # CORRECTION: col 0 = codigo_empaquetado (PK, unique), col 1 = codigo_articulo (FK to articulos.codigo)
    # So we want to know: how many articulos have MULTIPLE empaq rows = multi-codigo signal.
    art_to_emps: dict = {}
    for r in range(1, sh.nrows):
        emp = str(sh.cell_value(r, 0))      # codigo empaquetado (alt code)
        art = str(sh.cell_value(r, 1))      # codigo articulo (existing FK)
        art_to_emps.setdefault(art, set()).add(emp)
    multi_emp_articulos = {a: emps for a, emps in art_to_emps.items() if len(emps) > 1}
    print(
        f"\n  Articulos with MULTIPLE distinct codigos_empaquetados (multi-codigo signal): "
        f"{len(multi_emp_articulos)}"
    )
    sample_multi = list(multi_emp_articulos.items())[:8]
    for a, emps in sample_multi:
        print(f"    articulo_codigo {a} -> {len(emps)} empaq alt-codes: {list(emps)[:8]}")
    dist_emp_per_art = Counter(len(s) for s in art_to_emps.values())
    print(f"  Distribution of #empaq per articulo: {dict(sorted(dist_emp_per_art.items()))}")

    # ============ PHASE 3: RELACION cantidad ============
    target2 = "RELACION PRODUCTOS PROVEEDOR"
    if target2 not in wb.sheet_names():
        print(f"\nSHEET MISSING: {target2}")
        return 3

    sh2 = wb.sheet_by_name(target2)
    print(f"\n[PHASE 3] Sheet '{target2}' shape: rows={sh2.nrows}, cols={sh2.ncols}")

    headers2 = [decode_xls_str(sh2.cell_value(0, c)) for c in range(sh2.ncols)]
    print(f"[PHASE 3] Headers (decoded, with reprs to show trailing spaces):")
    for c, h in enumerate(headers2):
        print(f"    col {c}: {h!r}")

    # Find cantidad col index
    cant_idx = None
    for c, h in enumerate(headers2):
        if str(h).strip().lower() == "cantidad":
            cant_idx = c
            break
    print(f"[PHASE 3] cantidad column index: {cant_idx}")

    # Distribution of cantidad
    cant_counter: Counter = Counter()
    cant_zero = 0
    cant_null = 0
    cant_neg = 0
    cant_int_values = []
    cant_decimal_values = 0
    cant_str_values = 0
    if cant_idx is not None:
        for r in range(1, sh2.nrows):
            v = sh2.cell_value(r, cant_idx)
            if v in (None, ""):
                cant_null += 1
                continue
            if isinstance(v, (int, float)):
                fv = float(v)
                if fv == 0:
                    cant_zero += 1
                elif fv < 0:
                    cant_neg += 1
                else:
                    if fv != int(fv):
                        cant_decimal_values += 1
                    else:
                        cant_int_values.append(int(fv))
                cant_counter[fv] += 1
            else:
                cant_str_values += 1
                cant_counter[f"<str:{v!r}>"] += 1

    print(f"  null/empty: {cant_null}")
    print(f"  zero: {cant_zero}")
    print(f"  negative: {cant_neg}")
    print(f"  decimal (non-int): {cant_decimal_values}")
    print(f"  string: {cant_str_values}")
    print(f"  distinct values (excluding null): {len(cant_counter)}")
    print(
        f"  int values: count={len(cant_int_values)}, "
        f"min={min(cant_int_values) if cant_int_values else 'n/a'}, "
        f"max={max(cant_int_values) if cant_int_values else 'n/a'}"
    )
    print("\n  cantidad distribution (top 20):")
    for k, v in sorted(cant_counter.items(), key=lambda kv: -kv[1])[:20]:
        print(f"    {k!r:<30} count={v}")

    # Sample 12 rows of RELACION
    print("\n[PHASE 3] Sample rows (1..12) of RELACION:")
    for r in range(1, min(13, sh2.nrows)):
        row = [decode_xls_str(sh2.cell_value(r, c)) for c in range(sh2.ncols)]
        print(f"  row {r}: {row}")

    # Cross-tab: how many (articulo, proveedor) pairs have cantidad > 1?
    if cant_idx is not None:
        # find articulo col + proveedor col by header text
        art_idx = None
        prov_idx = None
        for c, h in enumerate(headers2):
            hl = str(h).strip().lower()
            if hl == "codigo articulo":
                art_idx = c
            elif hl == "codigo proveedor":
                prov_idx = c
        print(
            f"\n  art col: {art_idx}, proveedor col: {prov_idx}, cantidad col: {cant_idx}"
        )
        if art_idx is not None and prov_idx is not None:
            pair_to_cants: dict = {}
            for r in range(1, sh2.nrows):
                a = str(sh2.cell_value(r, art_idx))
                p = str(sh2.cell_value(r, prov_idx))
                c_ = sh2.cell_value(r, cant_idx)
                pair_to_cants.setdefault((a, p), []).append(c_)
            # how many (art,prov) appear multiple times with DIFFERENT cantidades?
            multi_cant_pairs = 0
            sample_multi_cant = []
            for k, vs in pair_to_cants.items():
                uvs = {v for v in vs if v not in (None, "")}
                if len(uvs) > 1:
                    multi_cant_pairs += 1
                    if len(sample_multi_cant) < 8:
                        sample_multi_cant.append((k, vs))
            print(
                f"  pairs (articulo, proveedor) appearing >1 time "
                f"WITH DIFFERENT cantidades: {multi_cant_pairs}"
            )
            for k, vs in sample_multi_cant:
                print(f"    {k} -> cantidades: {vs[:10]}")

            # Same articulo across MULTIPLE proveedores with DIFFERENT cantidades — RF-07 hot signal
            art_to_provcants: dict = {}
            for r in range(1, sh2.nrows):
                a = str(sh2.cell_value(r, art_idx))
                p = str(sh2.cell_value(r, prov_idx))
                c_ = sh2.cell_value(r, cant_idx)
                art_to_provcants.setdefault(a, []).append((p, c_))
            multi_prov_diff_cant = 0
            sample_rf07 = []
            for a, items in art_to_provcants.items():
                cants_per_prov = {}
                for p, c_ in items:
                    cants_per_prov.setdefault(p, set()).add(c_)
                # collapse to one cant per prov
                unique_cants = {next(iter(v)) for v in cants_per_prov.values()}
                if len(cants_per_prov) > 1 and len(unique_cants) > 1:
                    multi_prov_diff_cant += 1
                    if len(sample_rf07) < 8:
                        sample_rf07.append((a, cants_per_prov))
            print(
                f"\n  RF-07 SIGNAL — articulos sold by >1 proveedor with DIFFERENT cantidades: "
                f"{multi_prov_diff_cant}"
            )
            for a, prov_map in sample_rf07:
                row = ", ".join(
                    f"prov {p}={list(cs)[:3]}" for p, cs in prov_map.items()
                )
                print(f"    articulo {a}: {row}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
