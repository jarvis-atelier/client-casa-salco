"""HTTP routes for the Jarvis POS Agent.

Endpoints
---------
GET  /health              — basic ping
GET  /status              — printer state (driver, online, papel)
POST /print/ticket        — render + print a ticket; returns preview URL when mock
GET  /preview/<id>        — serve the mock-printer PDF
GET  /scale/status        — scale state (driver, port, online, last weight)
GET  /scale/weight        — read a single weight sample from the scale
POST /scale/tare          — tare the scale (zero the platter)
"""
from __future__ import annotations

import logging
import time

from flask import Blueprint, Flask, current_app, jsonify, request, send_file
from pydantic import ValidationError

from ..printer.base import PrinterError
from ..printer.mock import MockPrinter
from ..scale.base import IScaleDriver, ScaleError
from ..ticket.renderer import TicketPayload, render_ticket

log = logging.getLogger(__name__)

bp = Blueprint("agent", __name__)


# ---------------------------------------------------------------------------
@bp.get("/health")
def health() -> tuple[dict, int]:
    return {"ok": True, "service": "jarvis-pos-agent"}, 200


# ---------------------------------------------------------------------------
@bp.get("/status")
def status() -> tuple[dict, int]:
    driver = current_app.extensions["printer_driver"]
    s = driver.status()
    body = {
        "status": s.status,
        "driver": s.driver,
        "model": s.model,
        "papel": s.papel,
        "online": s.online,
        "detail": s.detail,
        "extra": s.extra,
    }
    return body, 200


# ---------------------------------------------------------------------------
@bp.post("/print/ticket")
def print_ticket() -> tuple[dict, int]:
    started = time.perf_counter()
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return {"printed": False, "error": "JSON body requerido"}, 400

    # Parse + validate
    try:
        payload = TicketPayload.model_validate(raw)
    except ValidationError as e:
        log.info("invalid ticket payload: %s", e)
        return {"printed": False, "error": "payload invalido", "details": e.errors()}, 422

    # Render (pure CPU)
    rendered = render_ticket(payload)

    driver = current_app.extensions["printer_driver"]
    try:
        result = driver.print_ticket(rendered)
    except PrinterError as e:
        log.warning("printer error: %s", e)
        return {"printed": False, "error": str(e), "code": e.code}, 502

    body: dict[str, object] = {
        "printed": result.printed,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "driver": driver.name,
        "metadata": rendered.metadata,
    }
    if result.preview_id:
        body["preview_id"] = result.preview_id
        body["preview_url"] = f"/preview/{result.preview_id}"
    return body, 200


# ---------------------------------------------------------------------------
@bp.get("/preview/<preview_id>")
def preview(preview_id: str):  # type: ignore[no-untyped-def]
    driver = current_app.extensions["printer_driver"]
    if not isinstance(driver, MockPrinter):
        return jsonify(error="preview disponible solo en modo mock"), 404

    pdf = driver.get_preview_path(preview_id)
    if not pdf:
        return jsonify(error=f"preview {preview_id} no encontrado"), 404

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"{preview_id}.pdf",
    )


# ---------------------------------------------------------------------------
# Scale endpoints
# ---------------------------------------------------------------------------


def _scale() -> IScaleDriver:
    return current_app.extensions["scale_driver"]


def _serialize_status(driver: IScaleDriver) -> dict:
    s = driver.status()
    return {
        "status": s.status,
        "driver": s.driver,
        "model": s.model,
        "online": s.online,
        "port": s.port,
        "last_weight_kg": (str(s.last_weight_kg) if s.last_weight_kg is not None else None),
        "detail": s.detail,
        "error": s.error,
        "extra": s.extra,
    }


@bp.get("/scale/status")
def scale_status() -> tuple[dict, int]:
    return _serialize_status(_scale()), 200


@bp.get("/scale/weight")
def scale_weight() -> tuple[dict, int]:
    driver = _scale()
    try:
        reading = driver.get_weight()
    except ScaleError as e:
        log.warning("scale read error: %s", e)
        return (
            {"ok": False, "error": str(e), "code": e.code, "driver": driver.name},
            502,
        )
    return (
        {
            "ok": True,
            "driver": driver.name,
            "weight_kg": str(reading.weight_kg),
            "stable": reading.stable,
            "tare_kg": str(reading.tare_kg),
            "unit": reading.unit,
            "timestamp": reading.timestamp.isoformat(),
            "raw": reading.raw_response,
        },
        200,
    )


@bp.post("/scale/tare")
def scale_tare() -> tuple[dict, int]:
    driver = _scale()
    try:
        ok = driver.tare()
    except ScaleError as e:
        log.warning("scale tare error: %s", e)
        return (
            {"ok": False, "error": str(e), "code": e.code, "driver": driver.name},
            502,
        )
    s = driver.status()
    return (
        {
            "ok": bool(ok),
            "driver": driver.name,
            "tare_kg": (
                str(s.last_weight_kg) if s.last_weight_kg is not None else "0.000"
            ),
        },
        200 if ok else 502,
    )


# ---------------------------------------------------------------------------
def register_routes(app: Flask) -> None:
    app.register_blueprint(bp)
