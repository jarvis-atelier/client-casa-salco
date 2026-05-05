"""Tests de mappers ETL contra los DBFs reales del sistema viejo.

NOTA: los DBFs entregados estan casi vacios (son un 'kit limpio'),
excepto RUBRO.DBF (23 rubros) y CLIENTES.DBF (1 cliente 'Consumidor Final').
Los tests validan que:
  - extract() lee los DBFs y emite dicts con los campos esperados.
  - load() inserta sin duplicar (idempotente al correr 2 veces).
  - Los mapeos de enums funcionan.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.models import (
    Articulo,
    ArticuloProveedor,
    Cliente,
    CondicionIvaEnum,
    Familia,
    Proveedor,
    Rubro,
)
from mappers import articulos as m_articulos
from mappers import articulos_proveedores as m_artprov
from mappers import clientes as m_clientes
from mappers import familias_rubros as m_famrub
from mappers import proveedores as m_proveedores

# Los DBFs entregados en el proyecto
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DBF_SOURCE = REPO_ROOT / "viejo" / "DBF"


@pytest.fixture
def dbf_source():
    assert DBF_SOURCE.exists(), f"DBF fixture dir missing: {DBF_SOURCE}"
    return DBF_SOURCE


# ---------------------------------------------------------------------------
# PROVEEDORES
# ---------------------------------------------------------------------------

class TestProveedores:
    def test_extract_returns_dicts(self, dbf_source):
        rows = list(m_proveedores.extract(dbf_source))
        # DBF entregado esta vacio (solo record template) -> 0 filas utiles
        for r in rows:
            assert "codigo" in r
            assert "razon_social" in r
            assert isinstance(r["codigo"], str)

    def test_load_is_idempotent(self, session, dbf_source):
        rows = list(m_proveedores.extract(dbf_source))
        # Insertamos uno sintetico para probar idempotencia efectiva
        sintetico = {
            "codigo": "999",
            "razon_social": "Proveedor Test",
            "cuit": "20-12345678-9",
            "telefono": None,
            "email": None,
            "direccion": "Calle falsa 123",
            "activo": True,
        }
        r1 = m_proveedores.load(session, [*rows, sintetico], dry_run=False)
        session.commit()
        count1 = session.query(Proveedor).count()
        assert r1.inserted >= 1
        # Segunda corrida: NO debe duplicar
        r2 = m_proveedores.load(session, [*rows, sintetico], dry_run=False)
        session.commit()
        count2 = session.query(Proveedor).count()
        assert count1 == count2
        assert r2.inserted == 0


# ---------------------------------------------------------------------------
# CLIENTES
# ---------------------------------------------------------------------------

class TestClientes:
    def test_extract_finds_consumidor_final(self, dbf_source):
        rows = list(m_clientes.extract(dbf_source))
        assert len(rows) >= 1
        desc_list = [r["razon_social"] for r in rows]
        assert any("CONSUMIDOR" in d.upper() for d in desc_list)

    def test_extract_maps_nuiv_to_condicion_iva(self, dbf_source):
        rows = list(m_clientes.extract(dbf_source))
        # Consumidor Final con nuiv=1 -> consumidor_final
        cf = next((r for r in rows if "CONSUMIDOR" in r["razon_social"].upper()), None)
        assert cf is not None
        assert cf["condicion_iva"] == CondicionIvaEnum.consumidor_final

    def test_load_and_reload_idempotent(self, session, dbf_source):
        rows = list(m_clientes.extract(dbf_source))
        r1 = m_clientes.load(session, rows, dry_run=False)
        session.commit()
        count1 = session.query(Cliente).count()
        assert r1.inserted >= 1

        r2 = m_clientes.load(session, rows, dry_run=False)
        session.commit()
        count2 = session.query(Cliente).count()
        assert count1 == count2
        assert r2.inserted == 0


# ---------------------------------------------------------------------------
# FAMILIAS Y RUBROS
# ---------------------------------------------------------------------------

class TestFamiliasRubros:
    def test_plan_always_has_fallbacks(self, dbf_source):
        plan = m_famrub.plan(dbf_source)
        codes = {f["codigo"] for f in plan.familias}
        assert "sin-familia" in codes
        assert "general" in codes

    def test_plan_loads_rubros_from_dbf(self, dbf_source):
        plan = m_famrub.plan(dbf_source)
        # RUBRO.DBF tiene 23 rubros reales
        rubro_names = [r["nombre"] for r in plan.rubros]
        # El fallback "Sin rubro" siempre esta
        assert "Sin rubro" in rubro_names
        # Y rubros como LACTEOS, FIAMBRES, etc. del DBF
        joined = " ".join(rubro_names).upper()
        assert "LACTEOS" in joined or "FIAMBRES" in joined

    def test_load_creates_familias_and_rubros(self, session, dbf_source):
        plan = m_famrub.plan(dbf_source)
        rep_f, rep_r = m_famrub.load(session, plan, dry_run=False)
        session.commit()
        assert rep_f.inserted >= 2  # general + sin-familia como minimo
        assert rep_r.inserted >= 1  # sin-rubro como minimo
        # Todos los rubros tienen familia
        for rubro in session.query(Rubro).all():
            assert rubro.familia_id is not None

    def test_load_idempotent(self, session, dbf_source):
        plan = m_famrub.plan(dbf_source)
        m_famrub.load(session, plan, dry_run=False)
        session.commit()
        count_f1 = session.query(Familia).count()
        count_r1 = session.query(Rubro).count()

        m_famrub.load(session, plan, dry_run=False)
        session.commit()
        count_f2 = session.query(Familia).count()
        count_r2 = session.query(Rubro).count()
        assert count_f1 == count_f2
        assert count_r1 == count_r2

    def test_build_rubro_lookup(self, session, dbf_source):
        plan = m_famrub.plan(dbf_source)
        m_famrub.load(session, plan, dry_run=False)
        session.commit()
        lookup = m_famrub.build_rubro_lookup(session, plan)
        # Lookup debe mapear por codigo legacy numerico (los que tenian _legacy_code)
        for k, v in lookup.items():
            assert isinstance(k, int)
            assert isinstance(v, Rubro)


# ---------------------------------------------------------------------------
# ARTICULOS
# ---------------------------------------------------------------------------

class TestArticulos:
    def test_extract_skips_template_record(self, dbf_source):
        # ARTICULO.DBF entregado tiene 1 "template" (codigo vacio o desc vacio).
        # extract() deberia saltarlo.
        rows = list(m_articulos.extract(dbf_source))
        # Aunque haya 1 registro "ARTICULOS VARIOS" (desc pero codigo=None),
        # extract exige codigo no-None -> 0 filas.
        for r in rows:
            assert r["codigo"]

    def test_load_resolves_fallback_rubro(self, session, dbf_source):
        from decimal import Decimal

        from app.models.articulo import UnidadMedidaEnum

        # Creamos rubros, y probamos articulo sintetico sin FK resoluble
        plan = m_famrub.plan(dbf_source)
        m_famrub.load(session, plan, dry_run=False)
        session.commit()

        sintetico = [{
            "codigo": "ART-001",
            "descripcion": "Articulo Test",
            # `_principal_codigo` reemplaza al ex-campo `codigo_barras`:
            # el mapper lo emite como signal privado y `load()` lo escribe
            # como `ArticuloCodigo(tipo='principal')` post-flush.
            "_principal_codigo": None,
            "_legacy_rubro": None,
            "_legacy_linea": None,
            "_legacy_proveedor": None,
            "unidad_medida": UnidadMedidaEnum.unidad,
            "costo": Decimal("10.00"),
            "pvp_base": Decimal("15.00"),
            "iva_porc": Decimal("21"),
            "activo": True,
            "controla_stock": True,
            "controla_vencimiento": False,
        }]

        r = m_articulos.load(session, sintetico, dry_run=False, rubro_lookup={})
        session.commit()
        assert r.inserted == 1
        art = session.query(Articulo).filter_by(codigo="ART-001").one()
        # Asignado al rubro fallback "sin-rubro"
        assert art.rubro is not None
        assert art.rubro.codigo == "sin-rubro"
        # Familia del rubro = "sin-familia"
        assert art.familia is not None
        assert art.familia.codigo == "sin-familia"

    def test_load_idempotent(self, session, dbf_source):
        from decimal import Decimal

        from app.models.articulo import UnidadMedidaEnum

        plan = m_famrub.plan(dbf_source)
        m_famrub.load(session, plan, dry_run=False)
        session.commit()

        rows = [{
            "codigo": "ART-002",
            "descripcion": "Yerba Playadito 1kg",
            # `_principal_codigo`: ex `codigo_barras`. El loader lo
            # consume y escribe un `ArticuloCodigo(tipo='principal')`.
            "_principal_codigo": "7790001111111",
            "_legacy_rubro": None,
            "_legacy_linea": None,
            "_legacy_proveedor": None,
            "unidad_medida": UnidadMedidaEnum.kg,
            "costo": Decimal("100.00"),
            "pvp_base": Decimal("150.00"),
            "iva_porc": Decimal("21"),
            "activo": True,
            "controla_stock": True,
            "controla_vencimiento": False,
        }]
        m_articulos.load(session, [dict(r) for r in rows], dry_run=False, rubro_lookup={})
        session.commit()
        count1 = session.query(Articulo).count()
        m_articulos.load(session, [dict(r) for r in rows], dry_run=False, rubro_lookup={})
        session.commit()
        count2 = session.query(Articulo).count()
        assert count1 == count2


# ---------------------------------------------------------------------------
# ARTICULOS x PROVEEDORES
# ---------------------------------------------------------------------------

class TestArticulosProveedores:
    def test_extract_empty_is_ok(self, dbf_source):
        # ARTIPROV.DBF esta vacio en el fixture -> 0 filas.
        rows = list(m_artprov.extract(dbf_source))
        assert rows == []

    def test_load_skips_missing_refs(self, session, dbf_source):
        # Inserta sinteticos con referencias inexistentes -> debe fallar gracefully
        rows = [{
            "_articulo_codigo": "NO-EXISTE",
            "_proveedor_codigo": "NO-EXISTE",
            "codigo_proveedor": "X",
            "costo_proveedor": 0,
            "ultimo_ingreso": None,
        }]
        r = m_artprov.load(session, rows, dry_run=False)
        session.commit()
        assert r.failed == 1
        assert session.query(ArticuloProveedor).count() == 0
