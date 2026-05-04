"""Tests del endpoint /precios/actualizar — sync multi-sucursal + histórico."""
from __future__ import annotations


def _setup_articulo_y_sucursales(client, admin_token, auth_header):
    # 2 sucursales
    r = client.post(
        "/api/v1/sucursales",
        headers=auth_header(admin_token),
        json={"codigo": "SUC01", "nombre": "Central"},
    )
    suc1 = r.get_json()["id"]
    r = client.post(
        "/api/v1/sucursales",
        headers=auth_header(admin_token),
        json={"codigo": "SUC02", "nombre": "Norte"},
    )
    suc2 = r.get_json()["id"]

    # 1 articulo
    r = client.post(
        "/api/v1/articulos",
        headers=auth_header(admin_token),
        json={
            "codigo": "A001",
            "descripcion": "Arroz 1kg",
            "unidad_medida": "unidad",
            "costo": "500",
            "pvp_base": "800",
        },
    )
    art_id = r.get_json()["id"]
    return art_id, suc1, suc2


def test_actualizar_precios_happy_path(client, admin_token, auth_header, db):
    art_id, suc1, suc2 = _setup_articulo_y_sucursales(client, admin_token, auth_header)

    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={
            "articulo_id": art_id,
            "cambios": [
                {"sucursal_id": suc1, "precio": "900.50"},
                {"sucursal_id": suc2, "precio": "950.00"},
            ],
            "motivo": "ajuste mensual",
        },
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["articulo_id"] == art_id
    assert body["actualizados"] == 2
    assert len(body["items"]) == 2
    # precio_anterior es None en el primer cambio
    assert body["items"][0]["precio_anterior"] is None
    assert body["items"][0]["precio_nuevo"] == "900.50"

    # Verificar precios vigentes vía GET /precios?articulo_id=
    r = client.get(
        f"/api/v1/precios?articulo_id={art_id}",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    precios = r.get_json()
    assert len(precios) == 2
    por_suc = {p["sucursal"]["id"]: p for p in precios}
    assert por_suc[suc1]["precio"] == "900.5000"
    assert por_suc[suc2]["precio"] == "950.0000"
    assert por_suc[suc1]["sucursal"]["codigo"] == "SUC01"
    assert por_suc[suc2]["sucursal"]["codigo"] == "SUC02"


def test_actualizar_sucursales_alias_legado(client, admin_token, auth_header):
    """El alias `sucursales` debe seguir funcionando como `cambios`."""
    art_id, suc1, _ = _setup_articulo_y_sucursales(client, admin_token, auth_header)
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={
            "articulo_id": art_id,
            "sucursales": [{"sucursal_id": suc1, "precio": "111"}],
        },
    )
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["actualizados"] == 1


def test_aplicar_a_todas_expande_a_sucursales_activas(client, admin_token, auth_header):
    """`aplicar_a_todas=true` + precio único expande a todas las sucursales activas."""
    art_id, suc1, suc2 = _setup_articulo_y_sucursales(client, admin_token, auth_header)
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={
            "articulo_id": art_id,
            "precio": "1234.56",
            "aplicar_a_todas": True,
            "motivo": "unificacion",
        },
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["actualizados"] == 2
    sucs_tocadas = {it["sucursal_id"] for it in body["items"]}
    assert sucs_tocadas == {suc1, suc2}

    # todas las filas nuevas deben quedar en 1234.56
    r = client.get(
        f"/api/v1/precios?articulo_id={art_id}",
        headers=auth_header(admin_token),
    )
    precios = r.get_json()
    assert all(p["precio"] == "1234.5600" for p in precios)


def test_actualizar_cierra_precio_anterior_unica_activa(
    client, admin_token, auth_header, db
):
    from app.models.precio import PrecioSucursal

    art_id, suc1, _ = _setup_articulo_y_sucursales(client, admin_token, auth_header)

    # primera actualización
    client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={"articulo_id": art_id, "cambios": [{"sucursal_id": suc1, "precio": "100"}]},
    )
    # segunda
    client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={"articulo_id": art_id, "cambios": [{"sucursal_id": suc1, "precio": "200"}]},
    )

    rows = (
        db.session.query(PrecioSucursal)
        .filter(PrecioSucursal.articulo_id == art_id, PrecioSucursal.sucursal_id == suc1)
        .all()
    )
    assert len(rows) == 2
    activos = [r for r in rows if r.activo]
    inactivos = [r for r in rows if not r.activo]
    assert len(activos) == 1
    assert len(inactivos) == 1
    assert str(activos[0].precio) == "200.0000"
    assert inactivos[0].vigente_hasta is not None


def test_multi_sucursal_una_sola_activa_por_combo(client, admin_token, auth_header, db):
    """Una fila activa por combo (articulo, sucursal)."""
    from app.models.precio import PrecioSucursal

    art_id, suc1, suc2 = _setup_articulo_y_sucursales(client, admin_token, auth_header)

    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={
            "articulo_id": art_id,
            "cambios": [
                {"sucursal_id": suc1, "precio": "100"},
                {"sucursal_id": suc2, "precio": "150"},
            ],
        },
    )
    assert r.status_code == 200

    # segundo update total a los dos
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={
            "articulo_id": art_id,
            "cambios": [
                {"sucursal_id": suc1, "precio": "110"},
                {"sucursal_id": suc2, "precio": "160"},
            ],
        },
    )
    assert r.status_code == 200

    rows = (
        db.session.query(PrecioSucursal)
        .filter(PrecioSucursal.articulo_id == art_id)
        .all()
    )
    assert len(rows) == 4  # 2 sucursales x 2 updates
    activos_por_suc: dict[int, int] = {}
    for r in rows:
        if r.activo:
            activos_por_suc[r.sucursal_id] = activos_por_suc.get(r.sucursal_id, 0) + 1
    assert activos_por_suc == {suc1: 1, suc2: 1}


def test_historico_se_guarda(client, admin_token, auth_header, db):
    from app.models.precio import PrecioHistorico

    art_id, suc1, _ = _setup_articulo_y_sucursales(client, admin_token, auth_header)

    client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={
            "articulo_id": art_id,
            "cambios": [{"sucursal_id": suc1, "precio": "150"}],
            "motivo": "inflacion",
        },
    )

    rows = (
        db.session.query(PrecioHistorico)
        .filter(PrecioHistorico.articulo_id == art_id)
        .all()
    )
    assert len(rows) == 1
    assert str(rows[0].precio_nuevo) == "150.0000"
    assert rows[0].motivo == "inflacion"


def test_actualizar_precios_cajero_403(client, cajero_token, auth_header):
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(cajero_token),
        json={"articulo_id": 1, "cambios": [{"sucursal_id": 1, "precio": "100"}]},
    )
    assert r.status_code == 403


def test_supervisor_puede_actualizar(client, admin_token, supervisor_token, auth_header):
    art_id, suc1, _ = _setup_articulo_y_sucursales(client, admin_token, auth_header)
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(supervisor_token),
        json={"articulo_id": art_id, "cambios": [{"sucursal_id": suc1, "precio": "300"}]},
    )
    assert r.status_code == 200


def test_admin_puede_actualizar(client, admin_token, auth_header):
    art_id, suc1, _ = _setup_articulo_y_sucursales(client, admin_token, auth_header)
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={"articulo_id": art_id, "cambios": [{"sucursal_id": suc1, "precio": "300"}]},
    )
    assert r.status_code == 200


def test_articulo_inexistente(client, admin_token, auth_header):
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={"articulo_id": 99999, "cambios": [{"sucursal_id": 1, "precio": "100"}]},
    )
    assert r.status_code == 404


def test_sucursal_inexistente(client, admin_token, auth_header):
    art_id, _, _ = _setup_articulo_y_sucursales(client, admin_token, auth_header)
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={
            "articulo_id": art_id,
            "cambios": [{"sucursal_id": 99999, "precio": "100"}],
        },
    )
    assert r.status_code == 404


def test_body_invalido_sin_cambios_ni_aplicar_a_todas(
    client, admin_token, auth_header
):
    r = client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={"articulo_id": 1, "motivo": "x"},
    )
    assert r.status_code == 422


def test_get_precios_por_articulo(client, admin_token, auth_header):
    art_id, suc1, suc2 = _setup_articulo_y_sucursales(client, admin_token, auth_header)
    client.post(
        "/api/v1/precios/actualizar",
        headers=auth_header(admin_token),
        json={
            "articulo_id": art_id,
            "cambios": [
                {"sucursal_id": suc1, "precio": "100"},
                {"sucursal_id": suc2, "precio": "200"},
            ],
        },
    )
    r = client.get(
        f"/api/v1/precios?articulo_id={art_id}",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    for item in data:
        assert "sucursal" in item
        assert {"id", "codigo", "nombre"}.issubset(item["sucursal"].keys())
        assert "precio" in item
        assert "vigente_desde" in item


def test_get_precios_sin_articulo_id(client, admin_token, auth_header):
    r = client.get("/api/v1/precios", headers=auth_header(admin_token))
    assert r.status_code == 422


def test_get_precios_articulo_sin_precios(client, admin_token, auth_header):
    art_id, _, _ = _setup_articulo_y_sucursales(client, admin_token, auth_header)
    r = client.get(
        f"/api/v1/precios?articulo_id={art_id}",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    assert r.get_json() == []
