"""Registro de blueprints de la API v1."""
from flask import Blueprint, Flask, jsonify

# Root de v1 para devolver hello hasta que existan endpoints reales
v1_root = Blueprint("v1_root", __name__, url_prefix="/api/v1")


@v1_root.get("/")
def index():
    return jsonify(api="castulo", version="v1", status="ok")


def register_blueprints(app: Flask) -> None:
    """Registra todos los blueprints de /api/v1 en la app."""
    from . import (
        alertas,
        areas,
        articulos,
        auth,
        caes,
        calendario_pagos,
        clientes,
        comercio,
        consultas,
        facturas,
        familias,
        marcas,
        movimientos,
        ocr,
        precios,
        proveedores,
        reports,
        reposicion,
        rubros,
        stock,
        subrubros,
        sucursales,
    )

    app.register_blueprint(v1_root)
    app.register_blueprint(auth.bp)
    app.register_blueprint(sucursales.bp)
    app.register_blueprint(areas.bp)
    app.register_blueprint(familias.bp)
    app.register_blueprint(rubros.bp)
    app.register_blueprint(subrubros.bp)
    app.register_blueprint(marcas.bp)
    app.register_blueprint(proveedores.bp)
    app.register_blueprint(articulos.bp)
    app.register_blueprint(precios.bp)
    app.register_blueprint(clientes.bp)
    app.register_blueprint(facturas.bp)
    app.register_blueprint(stock.bp)
    app.register_blueprint(movimientos.bp)
    app.register_blueprint(caes.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(comercio.bp)
    app.register_blueprint(alertas.bp)
    app.register_blueprint(ocr.bp)
    app.register_blueprint(calendario_pagos.bp)
    app.register_blueprint(consultas.bp)
    app.register_blueprint(reposicion.bp)
