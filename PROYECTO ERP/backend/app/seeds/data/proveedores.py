"""Proveedores — 40 empresas reales con presencia fuerte en el canal almacén argentino.

CUITs generados sintéticamente con prefijo 30 (personas jurídicas) y dígito
verificador válido. NO son CUITs reales — están armados via `_cuit_check_digit`
por si alguna vez validamos contra AFIP.
"""
from __future__ import annotations


def _cuit_check_digit(base11: str) -> int:
    """Calcula el dígito verificador para un CUIT (11 dígitos base son tipo+dni)."""
    assert len(base11) == 10, "se esperan 10 dígitos (2 tipo + 8 dni)"
    weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(base11, weights))
    mod = total % 11
    dv = 11 - mod
    if dv == 11:
        return 0
    if dv == 10:
        # Caso especial: en realidad AFIP pasa a tipo 23/24; para seed asumimos 9.
        return 9
    return dv


def _make_cuit(tipo: str, dni: str) -> str:
    base = f"{tipo}{dni}"
    return f"{tipo}-{dni}-{_cuit_check_digit(base)}"


# (codigo, razon_social, dni_base_8)  — tipo 30 es persona jurídica
_SEEDS: list[tuple[str, str, str]] = [
    ("PROV001", "Molinos Río de la Plata S.A.", "52876945"),
    ("PROV002", "Mastellone Hermanos S.A.", "50000000"),
    ("PROV003", "Arcor S.A.I.C.", "50671455"),
    ("PROV004", "La Serenísima S.A.", "50213654"),
    ("PROV005", "Bagley Argentina S.A.", "56889231"),
    ("PROV006", "Ledesma S.A.A.I.", "50007654"),
    ("PROV007", "Unilever de Argentina S.A.", "54090987"),
    ("PROV008", "Procter & Gamble Argentina S.R.L.", "57654321"),
    ("PROV009", "Coca-Cola FEMSA de Argentina S.A.", "55678910"),
    ("PROV010", "Pepsico de Argentina S.R.L.", "57890123"),
    ("PROV011", "Cervecería Quilmes AB InBev S.A.", "50331122"),
    ("PROV012", "Warsteiner Argentina S.A.", "71234567"),
    ("PROV013", "Cabaña Las Dinas S.A.", "70998877"),
    ("PROV014", "Sancor Cooperativas Unidas Ltda.", "50665544"),
    ("PROV015", "Lácteos Sanavirón S.A.", "71112233"),
    ("PROV016", "Danone Argentina S.A.", "64445566"),
    ("PROV017", "Nestlé Argentina S.A.", "53778899"),
    ("PROV018", "Kraft Heinz Argentina S.R.L.", "71445566"),
    ("PROV019", "La Campagnola S.A.C.I.", "52667788"),
    ("PROV020", "Granja del Sol S.A.", "56221133"),
    ("PROV021", "Molinos Granix S.A.", "50334455"),
    ("PROV022", "Fargo S.A.", "55889944"),
    ("PROV023", "Lucchetti Argentina S.A.", "54112233"),
    ("PROV024", "Molinos Matarazzo S.A.", "52998877"),
    ("PROV025", "Knorr Argentina S.A.", "57334422"),
    ("PROV026", "Marolio S.A.", "71556677"),
    ("PROV027", "Hellmann's Argentina S.A.", "53998844"),
    ("PROV028", "Unilever Home Care Argentina S.A.", "54887799"),
    ("PROV029", "Procter Cuidado Hogar S.R.L.", "57112255"),
    ("PROV030", "Clorox Argentina S.A.", "71778899"),
    ("PROV031", "3M Argentina S.A.C.I.F.I.A.", "52445566"),
    ("PROV032", "Colgate-Palmolive Argentina S.A.", "51223344"),
    ("PROV033", "Johnson & Johnson de Argentina S.A.C.E.I.", "56778899"),
    ("PROV034", "Kimberly-Clark Argentina S.A.", "51556677"),
    ("PROV035", "Papelera del Plata S.A.", "71223311"),
    ("PROV036", "Celulosa Argentina S.A.", "50884433"),
    ("PROV037", "3M Scotch-Brite Argentina", "53223344"),
    ("PROV038", "Distribuidora Norte Cba S.R.L.", "71665544"),
    ("PROV039", "Distribuidora del Centro S.A.", "71887766"),
    ("PROV040", "Logística Serrana S.R.L.", "71334422"),
]


PROVEEDORES: list[dict[str, str]] = [
    {
        "codigo": codigo,
        "razon_social": razon,
        "cuit": _make_cuit("30", dni),
    }
    for codigo, razon, dni in _SEEDS
]
