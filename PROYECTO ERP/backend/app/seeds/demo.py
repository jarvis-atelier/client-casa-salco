"""Seed demo mínimo — idempotente.

Admin + 4 sucursales con áreas + padrones mínimos + 5 artículos con precios
por sucursal + stock inicial 100u por (artículo, sucursal) + cliente CF.

Credenciales admin dev:
    email:    admin@casasalco.app
    password: admin123     (DEV-ONLY, cambiar antes de producción)
"""
from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models.articulo import Articulo, UnidadMedidaEnum
from app.models.articulo_codigo import ArticuloCodigo, TipoCodigoArticuloEnum
from app.models.categorias import Familia, Marca, Rubro, Subrubro
from app.models.cliente import Cliente, CondicionIvaEnum
from app.models.precio import PrecioSucursal
from app.models.proveedor import Proveedor
from app.models.stock import StockSucursal
from app.models.sucursal import Area, Sucursal
from app.models.user import RolEnum, User
from app.services.auth_service import hash_password

_SUCURSALES = [
    {
        "codigo": "SUC01",
        "nombre": "CASA SALCO Centro",
        "direccion": "Av. San Martín 1200",
        "ciudad": "Rio Cuarto",
        "provincia": "Cordoba",
        "tiene_fiambre": True,
    },
    {
        "codigo": "SUC02",
        "nombre": "CASA SALCO Norte",
        "direccion": "Av. Mitre 450",
        "ciudad": "Rio Cuarto",
        "provincia": "Cordoba",
        "tiene_fiambre": True,
    },
    {
        "codigo": "SUC03",
        "nombre": "CASA SALCO Sur",
        "direccion": "Bv. Roca 890",
        "ciudad": "Rio Cuarto",
        "provincia": "Cordoba",
        "tiene_fiambre": False,  # sucursal sin fiambrería
    },
    {
        "codigo": "SUC04",
        "nombre": "CASA SALCO Express",
        "direccion": "Av. España 210",
        "ciudad": "Rio Cuarto",
        "provincia": "Cordoba",
        "tiene_fiambre": True,
    },
]

_AREAS_BASE = [
    ("COM", "Comestibles", 10),
    ("FIA", "Fiambrería", 20),
    ("POL", "Pollería", 30),
    ("DRU", "Drugstore", 40),
]

_FAMILIAS = [
    ("ALM", "Almacén", 10),
    ("LACT", "Lácteos", 20),
    ("BEB", "Bebidas", 30),
    ("LIM", "Limpieza", 40),
]

_RUBROS = [
    ("ALM", "ARR", "Arroz"),
    ("ALM", "FID", "Fideos"),
    ("LACT", "LEC", "Leches"),
    ("LACT", "QUE", "Quesos"),
    ("BEB", "GAS", "Gaseosas"),
    ("LIM", "DET", "Detergentes"),
]

_SUBRUBROS = [
    ("ALM", "ARR", "BLA", "Arroz Blanco"),
    ("ALM", "ARR", "INT", "Arroz Integral"),
    ("ALM", "FID", "SEC", "Fideos Secos"),
    ("LACT", "LEC", "ENT", "Leche Entera"),
    ("LACT", "LEC", "DES", "Leche Descremada"),
    ("LACT", "QUE", "DUR", "Queso Duro"),
    ("LACT", "QUE", "BLA", "Queso Blando"),
    ("BEB", "GAS", "COL", "Gaseosa Cola"),
    ("BEB", "GAS", "LIM", "Gaseosa Lima-Limón"),
    ("LIM", "DET", "POL", "Detergente en Polvo"),
]

_MARCAS = ["Gallo", "La Serenísima", "Coca-Cola"]

_PROVEEDORES = [
    ("PROV01", "Molinos Rio de la Plata", "30-52876945-2"),
    ("PROV02", "Mastellone Hnos", "30-50000000-7"),
    ("PROV03", "Distribuidora Central SRL", "30-71234567-8"),
]

_ARTICULOS = [
    ("A001", "7790001001234", "Arroz Gallo Oro 1kg", "ALM", "ARR", "BLA", "Gallo", "PROV01",
     UnidadMedidaEnum.unidad, Decimal("600"), Decimal("890")),
    ("A002", "7790001001241", "Fideos Gallo Tirabuzón 500g", "ALM", "FID", "SEC", "Gallo", "PROV01",
     UnidadMedidaEnum.unidad, Decimal("350"), Decimal("550")),
    ("A003", "7790070001005", "Leche Serenísima Entera 1lt", "LACT", "LEC", "ENT",
     "La Serenísima", "PROV02",
     UnidadMedidaEnum.lt, Decimal("650"), Decimal("990")),
    ("A004", "7790070001012", "Leche Serenísima Descremada 1lt", "LACT", "LEC", "DES",
     "La Serenísima", "PROV02",
     UnidadMedidaEnum.lt, Decimal("680"), Decimal("1020")),
    ("A005", "7790040001001", "Coca-Cola 2.25lt", "BEB", "GAS", "COL", "Coca-Cola", "PROV03",
     UnidadMedidaEnum.unidad, Decimal("1100"), Decimal("1850")),
]


def seed_demo() -> None:
    """Idempotente — no duplica si ya hay datos. Incluye stock inicial 100u."""
    # Admin
    admin = db.session.query(User).filter(User.email == "admin@casasalco.app").first()
    if admin is None:
        admin = User(
            email="admin@casasalco.app",
            password_hash=hash_password("admin123"),  # DEV-ONLY
            nombre="Administrador Demo",
            rol=RolEnum.admin,
            activo=True,
        )
        db.session.add(admin)

    # Sucursales + Áreas
    sucursales_by_code: dict[str, Sucursal] = {}
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
        sucursales_by_code[data["codigo"]] = suc

    db.session.flush()

    for data in _SUCURSALES:
        suc = sucursales_by_code[data["codigo"]]
        for codigo, nombre, orden in _AREAS_BASE:
            if codigo == "FIA" and not data["tiene_fiambre"]:
                continue
            existe = (
                db.session.query(Area)
                .filter(Area.sucursal_id == suc.id, Area.codigo == codigo)
                .first()
            )
            if existe is None:
                db.session.add(
                    Area(sucursal_id=suc.id, codigo=codigo, nombre=nombre, orden=orden, activa=True)
                )

    # Familias
    familias_by_code: dict[str, Familia] = {}
    for codigo, nombre, orden in _FAMILIAS:
        fam = db.session.query(Familia).filter(Familia.codigo == codigo).first()
        if fam is None:
            fam = Familia(codigo=codigo, nombre=nombre, orden=orden)
            db.session.add(fam)
        familias_by_code[codigo] = fam
    db.session.flush()

    # Rubros
    rubros_by_key: dict[tuple[str, str], Rubro] = {}
    for fam_cod, rub_cod, nombre in _RUBROS:
        fam = familias_by_code[fam_cod]
        rub = (
            db.session.query(Rubro)
            .filter(Rubro.familia_id == fam.id, Rubro.codigo == rub_cod)
            .first()
        )
        if rub is None:
            rub = Rubro(familia_id=fam.id, codigo=rub_cod, nombre=nombre, orden=0)
            db.session.add(rub)
        rubros_by_key[(fam_cod, rub_cod)] = rub
    db.session.flush()

    # Subrubros
    subrubros_by_key: dict[tuple[str, str, str], Subrubro] = {}
    for fam_cod, rub_cod, sub_cod, nombre in _SUBRUBROS:
        rub = rubros_by_key[(fam_cod, rub_cod)]
        sub = (
            db.session.query(Subrubro)
            .filter(Subrubro.rubro_id == rub.id, Subrubro.codigo == sub_cod)
            .first()
        )
        if sub is None:
            sub = Subrubro(rubro_id=rub.id, codigo=sub_cod, nombre=nombre, orden=0)
            db.session.add(sub)
        subrubros_by_key[(fam_cod, rub_cod, sub_cod)] = sub

    # Marcas
    marcas_by_name: dict[str, Marca] = {}
    for nombre in _MARCAS:
        marca = db.session.query(Marca).filter(Marca.nombre == nombre).first()
        if marca is None:
            marca = Marca(nombre=nombre, activa=True)
            db.session.add(marca)
        marcas_by_name[nombre] = marca
    db.session.flush()

    # Proveedores
    proveedores_by_code: dict[str, Proveedor] = {}
    for codigo, razon, cuit in _PROVEEDORES:
        prov = db.session.query(Proveedor).filter(Proveedor.codigo == codigo).first()
        if prov is None:
            prov = Proveedor(codigo=codigo, razon_social=razon, cuit=cuit, activo=True)
            db.session.add(prov)
        proveedores_by_code[codigo] = prov
    db.session.flush()

    # Artículos
    articulos_created: list[Articulo] = []
    for (
        codigo, barras, desc, fam, rub, sub, marca_n, prov_c, unidad, costo, pvp,
    ) in _ARTICULOS:
        art = db.session.query(Articulo).filter(Articulo.codigo == codigo).first()
        if art is None:
            art = Articulo(
                codigo=codigo,
                descripcion=desc,
                familia_id=familias_by_code[fam].id,
                rubro_id=rubros_by_key[(fam, rub)].id,
                subrubro_id=subrubros_by_key[(fam, rub, sub)].id,
                marca_id=marcas_by_name[marca_n].id,
                proveedor_principal_id=proveedores_by_code[prov_c].id,
                unidad_medida=unidad,
                costo=costo,
                pvp_base=pvp,
                activo=True,
            )
            # Codigo principal va al hijo `articulo_codigos`
            # (la columna Articulo.codigo_barras ya no existe).
            if barras:
                art.codigos.append(
                    ArticuloCodigo(
                        codigo=barras,
                        tipo=TipoCodigoArticuloEnum.principal,
                    )
                )
            db.session.add(art)
        articulos_created.append(art)

    db.session.flush()

    # Precios por sucursal
    for art in articulos_created:
        for suc in sucursales_by_code.values():
            existe = (
                db.session.query(PrecioSucursal)
                .filter(
                    PrecioSucursal.articulo_id == art.id,
                    PrecioSucursal.sucursal_id == suc.id,
                    PrecioSucursal.activo.is_(True),
                )
                .first()
            )
            if existe is None:
                db.session.add(
                    PrecioSucursal(
                        articulo_id=art.id,
                        sucursal_id=suc.id,
                        precio=art.pvp_base,
                        activo=True,
                    )
                )

    # Cliente consumidor final de ejemplo
    cli = db.session.query(Cliente).filter(Cliente.codigo == "CF").first()
    if cli is None:
        db.session.add(
            Cliente(
                codigo="CF",
                razon_social="Consumidor Final",
                condicion_iva=CondicionIvaEnum.consumidor_final,
                activo=True,
            )
        )

    db.session.flush()

    # Stock inicial — 100 unidades por artículo en cada sucursal para demo POS.
    for art in articulos_created:
        for suc in sucursales_by_code.values():
            existe = (
                db.session.query(StockSucursal)
                .filter(
                    StockSucursal.articulo_id == art.id,
                    StockSucursal.sucursal_id == suc.id,
                )
                .first()
            )
            if existe is None:
                db.session.add(
                    StockSucursal(
                        articulo_id=art.id,
                        sucursal_id=suc.id,
                        cantidad=Decimal("100"),
                    )
                )

    db.session.commit()
