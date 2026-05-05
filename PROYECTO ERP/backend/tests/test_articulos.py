"""Tests de CRUD y búsqueda de artículos."""
from __future__ import annotations

from faker import Faker

fake = Faker("es_AR")


def _create_articulo(client, token, auth_header, **overrides):
    payload = {
        "codigo": overrides.get("codigo", f"ART{fake.unique.random_int(100, 99999)}"),
        "descripcion": overrides.get("descripcion", fake.catch_phrase()),
        "codigo_principal": overrides.get("codigo_principal"),
        "unidad_medida": "unidad",
        "costo": "10.00",
        "pvp_base": "15.00",
    }
    r = client.post(
        "/api/v1/articulos", headers=auth_header(token), json=payload
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_crud_articulo(client, admin_token, auth_header):
    art = _create_articulo(
        client, admin_token, auth_header,
        codigo="A001", descripcion="Arroz Gallo 1kg", codigo_principal="7790001",
    )
    assert art["codigo"] == "A001"
    # codigo_principal viaja como hijo en `codigos[]` con tipo='principal'
    assert len(art["codigos"]) == 1
    assert art["codigos"][0]["codigo"] == "7790001"
    assert art["codigos"][0]["tipo"] == "principal"

    # list paginada
    r = client.get("/api/v1/articulos?page=1&per_page=10", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 1
    assert body["items"][0]["codigo"] == "A001"

    # get
    r = client.get(f"/api/v1/articulos/{art['id']}", headers=auth_header(admin_token))
    assert r.status_code == 200

    # patch
    r = client.patch(
        f"/api/v1/articulos/{art['id']}",
        headers=auth_header(admin_token),
        json={"descripcion": "Arroz Gallo Oro 1kg"},
    )
    assert r.status_code == 200
    assert r.get_json()["descripcion"] == "Arroz Gallo Oro 1kg"

    # delete soft
    r = client.delete(f"/api/v1/articulos/{art['id']}", headers=auth_header(admin_token))
    assert r.status_code == 204

    r = client.get("/api/v1/articulos", headers=auth_header(admin_token))
    assert r.get_json()["total"] == 0


def test_articulo_busqueda(client, admin_token, auth_header):
    _create_articulo(
        client, admin_token, auth_header, codigo="A001", descripcion="Arroz Gallo"
    )
    _create_articulo(
        client, admin_token, auth_header, codigo="A002", descripcion="Fideos Molto"
    )
    _create_articulo(
        client, admin_token, auth_header, codigo="A003", descripcion="Arroz Lucchetti"
    )

    r = client.get("/api/v1/articulos?q=arroz", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 2
    codigos = {i["codigo"] for i in body["items"]}
    assert codigos == {"A001", "A003"}


def test_articulo_paginacion(client, admin_token, auth_header):
    for i in range(12):
        _create_articulo(client, admin_token, auth_header, codigo=f"B{i:03d}")

    r = client.get("/api/v1/articulos?page=1&per_page=5", headers=auth_header(admin_token))
    body = r.get_json()
    assert body["total"] == 12
    assert body["pages"] == 3
    assert body["per_page"] == 5
    assert len(body["items"]) == 5


def test_articulo_codigo_duplicado(client, admin_token, auth_header):
    _create_articulo(client, admin_token, auth_header, codigo="X001")
    r = client.post(
        "/api/v1/articulos",
        headers=auth_header(admin_token),
        json={
            "codigo": "X001",
            "descripcion": "Duplicado",
            "unidad_medida": "unidad",
            "costo": "10",
            "pvp_base": "15",
        },
    )
    assert r.status_code == 409


def test_cajero_no_puede_crear_articulo(client, cajero_token, auth_header):
    r = client.post(
        "/api/v1/articulos",
        headers=auth_header(cajero_token),
        json={
            "codigo": "X001",
            "descripcion": "Should not",
            "unidad_medida": "unidad",
            "costo": "10",
            "pvp_base": "15",
        },
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tests específicos del flujo `codigo_principal` (Change A)
# ---------------------------------------------------------------------------


def test_create_articulo_with_codigo_principal_creates_child_row(
    client, admin_token, auth_header
):
    """POST /articulos con `codigo_principal` crea UN hijo con tipo='principal'."""
    r = client.post(
        "/api/v1/articulos",
        headers=auth_header(admin_token),
        json={
            "codigo": "P001",
            "descripcion": "Producto con principal",
            "codigo_principal": "7790070103925",
            "unidad_medida": "unidad",
            "costo": "10",
            "pvp_base": "15",
        },
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert "codigos" in body
    assert len(body["codigos"]) == 1
    child = body["codigos"][0]
    assert child["codigo"] == "7790070103925"
    assert child["tipo"] == "principal"


def test_create_articulo_without_codigo_principal_creates_no_child_rows(
    client, admin_token, auth_header
):
    """POST /articulos sin `codigo_principal` (None) NO crea ninguna row hija.

    `codigo_principal` es opcional en Change A.
    """
    r = client.post(
        "/api/v1/articulos",
        headers=auth_header(admin_token),
        json={
            "codigo": "P002",
            "descripcion": "Producto sin principal",
            # codigo_principal omitido (None)
            "unidad_medida": "unidad",
            "costo": "10",
            "pvp_base": "15",
        },
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body.get("codigos", []) == []


def test_create_articulo_with_explicit_null_codigo_principal_creates_no_child_rows(
    client, admin_token, auth_header
):
    """POST /articulos con `codigo_principal: null` explícito tampoco crea hijo."""
    r = client.post(
        "/api/v1/articulos",
        headers=auth_header(admin_token),
        json={
            "codigo": "P003",
            "descripcion": "Producto null",
            "codigo_principal": None,
            "unidad_medida": "unidad",
            "costo": "10",
            "pvp_base": "15",
        },
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body.get("codigos", []) == []


# ---------------------------------------------------------------------------
# /by-codigo/<c> endpoint (S6 — POS exact-match scan flow)
# ---------------------------------------------------------------------------


def test_get_articulo_by_codigo_returns_match(client, admin_token, auth_header):
    """GET /articulos/by-codigo/<c> devuelve el articulo dueño del codigo."""
    art = _create_articulo(
        client,
        admin_token,
        auth_header,
        codigo="BC001",
        descripcion="By-codigo target",
        codigo_principal="ABC123",
    )

    r = client.get(
        "/api/v1/articulos/by-codigo/ABC123",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["id"] == art["id"]
    assert body["codigo"] == "BC001"


def test_get_articulo_by_codigo_404_when_unknown(client, admin_token, auth_header):
    """GET /articulos/by-codigo/<c> devuelve 404 si no existe."""
    r = client.get(
        "/api/v1/articulos/by-codigo/NONEXISTENT",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 404


def test_get_articulo_by_codigo_returns_first_when_shared(
    client, admin_token, auth_header
):
    """Cuando dos artículos comparten el mismo codigo (UNIQUE es por par,
    no global), el endpoint devuelve el PRIMERO encontrado (LIMIT 1).
    """
    art1 = _create_articulo(
        client,
        admin_token,
        auth_header,
        codigo="SH001",
        descripcion="Shared 1",
        codigo_principal="SHARE999",
    )
    _create_articulo(
        client,
        admin_token,
        auth_header,
        codigo="SH002",
        descripcion="Otro distinto",
        codigo_principal="OTHER",
    )
    art3 = _create_articulo(
        client,
        admin_token,
        auth_header,
        codigo="SH003",
        descripcion="Shared 2 (mismo SHARE999)",
        codigo_principal="SHARE999",
    )

    r = client.get(
        "/api/v1/articulos/by-codigo/SHARE999",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.get_json()
    # Devuelve UN articulo, y debe ser uno de los dos que comparten el codigo.
    assert body["id"] in {art1["id"], art3["id"]}


def test_get_articulo_by_codigo_cajero_allowed(client, cajero_token, auth_header):
    """El cajero (rol POS) DEBE poder consultar `/by-codigo` (hot path scan)."""
    # Cajero no puede crear, pero sí debe poder buscar — primero creamos con admin.
    # Reusamos el cajero_token fixture y validamos que el rol pasa el guard.
    r = client.get(
        "/api/v1/articulos/by-codigo/CUALQUIERA",
        headers=auth_header(cajero_token),
    )
    # 404 (no existe) está OK — lo que valida es que NO haya 401/403.
    assert r.status_code in (200, 404)
