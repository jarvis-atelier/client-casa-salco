"""Quick check: EMPAQUETADOS col 0 (codigo empaquetado) value classes."""
from __future__ import annotations
from pathlib import Path
import xlrd
import re

FILE1 = Path(r"D:\repo\00-omar\CASA SALCO\3EB052EF592E1D591FBB8C-h00ugz.xls")
wb = xlrd.open_workbook(str(FILE1), on_demand=True)
sh = wb.sheet_by_name("EMPAQUETADOS DE PRODUCTOS")

EAN_PURE = re.compile(r"^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$")
DIGITS_ANY = re.compile(r"^\d+$")
ALPHA_LIKE = re.compile(r"[A-Za-z]")

cls_emp = {"ean8_12_13_14": 0, "digits_other": 0, "alpha_anywhere": 0,
           "starts_or_ends_quote": 0, "starts_asterisk": 0, "starts_space": 0,
           "empty": 0, "other": 0}
cls_art = {"ean8_12_13_14": 0, "digits_other": 0, "alpha_anywhere": 0, "empty": 0, "other": 0}

# Sample 30 alpha-like empaq codes for visual confirmation
alpha_empaqs = []

for r in range(1, sh.nrows):
    e = str(sh.cell_value(r, 0)).strip()
    a = str(sh.cell_value(r, 1)).strip()

    # classify e
    if not e:
        cls_emp["empty"] += 1
    elif e.startswith('"') or e.endswith('"'):
        cls_emp["starts_or_ends_quote"] += 1
        if len(alpha_empaqs) < 30:
            alpha_empaqs.append(("quote", e))
    elif e.startswith("*"):
        cls_emp["starts_asterisk"] += 1
    elif e.startswith(" "):
        cls_emp["starts_space"] += 1
    elif EAN_PURE.match(e):
        cls_emp["ean8_12_13_14"] += 1
    elif DIGITS_ANY.match(e):
        cls_emp["digits_other"] += 1
    elif ALPHA_LIKE.search(e):
        cls_emp["alpha_anywhere"] += 1
        if len(alpha_empaqs) < 30:
            alpha_empaqs.append(("alpha", e))
    else:
        cls_emp["other"] += 1

    # classify a
    if not a:
        cls_art["empty"] += 1
    elif EAN_PURE.match(a):
        cls_art["ean8_12_13_14"] += 1
    elif DIGITS_ANY.match(a):
        cls_art["digits_other"] += 1
    elif ALPHA_LIKE.search(a):
        cls_art["alpha_anywhere"] += 1
    else:
        cls_art["other"] += 1

print("EMPAQUETADOS col 0 (codigo empaquetado, length 22682):")
for k, v in cls_emp.items():
    print(f"  {k:<22} {v}")
print()
print("EMPAQUETADOS col 1 (codigo articulo, length 22682):")
for k, v in cls_art.items():
    print(f"  {k:<22} {v}")
print()
print(f"Sample alpha/quoted empaq codes (first {len(alpha_empaqs)}):")
for cat, s in alpha_empaqs:
    print(f"  [{cat}] {s!r}")
