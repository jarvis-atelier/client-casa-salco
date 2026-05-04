"""Servicio de orquestación OCR — upload, extract, confirmar, descartar."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import INSTANCE_DIR
from app.models.articulo import Articulo, UnidadMedidaEnum
from app.models.comprobante_ocr import (
    ComprobanteOcr,
    EstadoOcrEnum,
    TipoComprobanteOcrEnum,
)
from app.models.factura import EstadoComprobanteEnum, Factura, TipoComprobanteEnum
from app.models.factura_item import FacturaItem
from app.services import stock_service
from app.services.numeracion import next_numero

from . import OcrExtractionError
from .factory import get_ocr_provider
from .matcher import enriquecer_items_con_match, match_proveedor

logger = logging.getLogger(__name__)

UPLOAD_DIR = INSTANCE_DIR / "ocr_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "image/jpg", "application/pdf"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


class OcrServiceError(Exception):
    """Error de validación o negocio del servicio OCR."""


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Q2, rounding=ROUND_HALF_UP)


def _r4(v: Decimal) -> Decimal:
    return v.quantize(Q4, rounding=ROUND_HALF_UP)


def _safe_decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _safe_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }.get(mime, ".bin")


def _save_upload(content: bytes, mime: str) -> Path:
    name = f"{uuid.uuid4().hex}{_ext_from_mime(mime)}"
    target = UPLOAD_DIR / name
    target.write_bytes(content)
    return target


def upload_y_extraer(
    session: Session,
    *,
    file_bytes: bytes,
    mime: str,
    user_id: int,
    sucursal_id: int | None = None,
) -> ComprobanteOcr:
    """Guarda el archivo, llama al provider OCR y persiste resultado."""
    if mime not in ALLOWED_MIMES:
        raise OcrServiceError(
            f"mime '{mime}' no soportado (permitidos: {sorted(ALLOWED_MIMES)})"
        )
    if len(file_bytes) == 0:
        raise OcrServiceError("archivo vacío")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise OcrServiceError(
            f"archivo muy grande ({len(file_bytes)} bytes, máx {MAX_UPLOAD_BYTES})"
        )

    saved_path = _save_upload(file_bytes, mime)
    rel_path = saved_path.name  # solo el nombre, base es UPLOAD_DIR.

    comprobante = ComprobanteOcr(
        archivo_path=rel_path,
        archivo_size_bytes=len(file_bytes),
        archivo_mime=mime,
        estado=EstadoOcrEnum.procesando,
        uploaded_by_user_id=user_id,
        sucursal_id=sucursal_id,
        items_extraidos=[],
    )
    session.add(comprobante)
    session.flush()

    provider = get_ocr_provider()

    started = time.perf_counter()
    try:
        data = provider.extract(file_bytes, mime)
    except OcrExtractionError as exc:
        comprobante.estado = EstadoOcrEnum.error
        comprobante.error_message = str(exc)
        comprobante.modelo_ia_usado = provider.name
        comprobante.duracion_extraccion_ms = int((time.perf_counter() - started) * 1000)
        session.commit()
        return comprobante
    except Exception as exc:  # pragma: no cover — defensivo
        logger.exception("OCR provider falló")
        comprobante.estado = EstadoOcrEnum.error
        comprobante.error_message = f"error inesperado: {exc}"
        comprobante.modelo_ia_usado = provider.name
        comprobante.duracion_extraccion_ms = int((time.perf_counter() - started) * 1000)
        session.commit()
        return comprobante

    duration_ms = int((time.perf_counter() - started) * 1000)

    # Tipo
    tipo_str = (data.get("tipo") or "desconocido").lower()
    try:
        tipo_enum = TipoComprobanteOcrEnum(tipo_str)
    except ValueError:
        tipo_enum = TipoComprobanteOcrEnum.desconocido

    # Proveedor match
    proveedor_block = data.get("proveedor") or {}
    razon = proveedor_block.get("razon_social")
    cuit = proveedor_block.get("cuit")
    proveedor_match = match_proveedor(session, razon, cuit)

    # Items: enriquecer con match de artículos
    raw_items = data.get("items") or []
    items_norm: list[dict] = []
    for raw in raw_items:
        items_norm.append(
            {
                "descripcion": str(raw.get("descripcion") or "").strip(),
                "cantidad": float(_safe_decimal(raw.get("cantidad"), Decimal("1")) or 1),
                "unidad": str(raw.get("unidad") or "unidad").lower(),
                "precio_unitario": str(
                    _safe_decimal(raw.get("precio_unitario"), Decimal("0")) or "0"
                ),
                "subtotal": str(
                    _safe_decimal(raw.get("subtotal"), Decimal("0")) or "0"
                ),
            }
        )
    items_with_match = enriquecer_items_con_match(session, items_norm)

    confianza_raw = _safe_decimal(data.get("confianza"))
    if confianza_raw is not None:
        try:
            confianza = Decimal(confianza_raw).quantize(Decimal("0.0001"))
        except Exception:
            confianza = None
    else:
        confianza = None

    comprobante.estado = EstadoOcrEnum.extraido
    comprobante.tipo_detectado = tipo_enum
    comprobante.letra = (data.get("letra") or None)
    comprobante.confianza = confianza
    comprobante.proveedor_nombre_raw = razon
    comprobante.proveedor_cuit_raw = cuit
    comprobante.proveedor_id_match = proveedor_match.id if proveedor_match else None
    comprobante.numero_comprobante = data.get("numero_comprobante")
    comprobante.fecha_comprobante = _safe_date(data.get("fecha"))
    comprobante.subtotal = _safe_decimal(data.get("subtotal"))
    comprobante.iva_total = _safe_decimal(data.get("iva_total"))
    comprobante.total = _safe_decimal(data.get("total"))
    comprobante.items_extraidos = items_with_match
    comprobante.raw_response = data.get("raw_response") or {}
    comprobante.duracion_extraccion_ms = duration_ms
    comprobante.modelo_ia_usado = data.get("modelo") or provider.name

    session.commit()
    return comprobante


def descartar(session: Session, comprobante: ComprobanteOcr) -> ComprobanteOcr:
    if comprobante.estado in {EstadoOcrEnum.confirmado}:
        raise OcrServiceError("comprobante ya confirmado, no se puede descartar")
    comprobante.estado = EstadoOcrEnum.descartado
    session.commit()
    return comprobante


def _calc_linea(
    cantidad: Decimal,
    precio_unitario: Decimal,
    descuento_porc: Decimal,
    iva_porc: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Devuelve (subtotal, iva_monto, total) en 4 decimales."""
    bruto = cantidad * precio_unitario
    descuento_monto = bruto * (descuento_porc / Decimal("100"))
    subtotal = bruto - descuento_monto
    iva_monto = subtotal * (iva_porc / Decimal("100"))
    total = subtotal + iva_monto
    return _r4(subtotal), _r4(iva_monto), _r4(total)


def _crear_articulo_desde_item(
    session: Session,
    descripcion: str,
    unidad: str,
    iva_porc: Decimal,
    costo: Decimal,
    proveedor_id: int | None,
) -> Articulo:
    """Crea un artículo nuevo a partir de un ítem OCR sin match."""
    try:
        unidad_enum = UnidadMedidaEnum(unidad)
    except ValueError:
        unidad_enum = UnidadMedidaEnum.unidad

    # codigo único: OCR-<timestamp ms>-<n>
    base_code = f"OCR-{int(time.time() * 1000)}"
    codigo = base_code
    suffix = 0
    from sqlalchemy import select as _sel

    while session.execute(
        _sel(Articulo).where(Articulo.codigo == codigo)
    ).scalar_one_or_none() is not None:
        suffix += 1
        codigo = f"{base_code}-{suffix}"

    art = Articulo(
        codigo=codigo,
        descripcion=descripcion[:255] or "Artículo OCR sin descripción",
        unidad_medida=unidad_enum,
        controla_stock=True,
        controla_vencimiento=False,
        costo=costo,
        pvp_base=costo,
        iva_porc=iva_porc,
        activo=True,
        proveedor_principal_id=proveedor_id,
    )
    session.add(art)
    session.flush()
    return art


def confirmar(
    session: Session,
    comprobante: ComprobanteOcr,
    *,
    sucursal_id: int,
    items: list[dict],
    proveedor_id: int | None = None,
    numero_override: str | None = None,
    fecha_override: date | None = None,
    observacion: str | None = None,
    user_id: int,
) -> ComprobanteOcr:
    """Confirma el OCR creando una Factura tipo factura_c (compra).

    items es una lista de dicts (ya validados por OcrItemOverride):
        descripcion, cantidad, unidad, precio_unitario, iva_porc,
        descuento_porc, articulo_id, crear_articulo_si_falta.
    """
    if comprobante.estado not in {EstadoOcrEnum.extraido, EstadoOcrEnum.error}:
        raise OcrServiceError(
            f"comprobante en estado {comprobante.estado.value} no se puede confirmar"
        )
    if comprobante.factura_creada_id is not None:
        raise OcrServiceError("comprobante ya tiene factura asociada")
    if not items:
        raise OcrServiceError("se requiere al menos un item")

    proveedor_efectivo = proveedor_id or comprobante.proveedor_id_match

    # Resolver/crear artículos para cada item.
    items_resueltos: list[dict[str, Any]] = []
    subtotal_total = Decimal("0")
    iva_total = Decimal("0")
    total_total = Decimal("0")

    for idx, raw in enumerate(items):
        cantidad = Decimal(str(raw["cantidad"]))
        precio = Decimal(str(raw["precio_unitario"]))
        iva_porc = Decimal(str(raw.get("iva_porc", "21")))
        descuento_porc = Decimal(str(raw.get("descuento_porc", "0")))

        art_id = raw.get("articulo_id")
        articulo: Articulo | None = None
        if art_id:
            articulo = session.get(Articulo, int(art_id))
            if articulo is None or articulo.deleted_at is not None:
                raise OcrServiceError(f"articulo {art_id} inválido")

        if articulo is None:
            if not raw.get("crear_articulo_si_falta", True):
                raise OcrServiceError(
                    f"item '{raw.get('descripcion')}' sin articulo_id y crear_articulo_si_falta=False"
                )
            articulo = _crear_articulo_desde_item(
                session,
                descripcion=str(raw["descripcion"]),
                unidad=str(raw.get("unidad", "unidad")),
                iva_porc=iva_porc,
                costo=precio,
                proveedor_id=proveedor_efectivo,
            )

        subtotal, iva_monto, total = _calc_linea(
            cantidad, precio, descuento_porc, iva_porc
        )
        subtotal_total += subtotal
        iva_total += iva_monto
        total_total += total

        items_resueltos.append(
            {
                "articulo": articulo,
                "cantidad": cantidad,
                "precio_unitario": precio,
                "descuento_porc": descuento_porc,
                "iva_porc": iva_porc,
                "iva_monto": iva_monto,
                "subtotal": subtotal,
                "total": total,
                "orden": idx,
                "descripcion": str(raw["descripcion"])[:255],
            }
        )

    subtotal_total = _r2(subtotal_total)
    iva_total = _r2(iva_total)
    total_total = _r2(total_total)

    # Numeración de la factura compra (tipo factura_c, pv=1).
    tipo = TipoComprobanteEnum.factura_c
    numero = next_numero(session, sucursal_id, 1, tipo)

    fecha_dt = (
        datetime.combine(fecha_override, datetime.min.time(), tzinfo=UTC)
        if fecha_override
        else (
            datetime.combine(comprobante.fecha_comprobante, datetime.min.time(), tzinfo=UTC)
            if comprobante.fecha_comprobante
            else datetime.now(UTC)
        )
    )

    obs_parts = [
        f"OCR #{comprobante.id}",
        f"Comprobante: {numero_override or comprobante.numero_comprobante or 's/n'}",
    ]
    if comprobante.proveedor_nombre_raw:
        obs_parts.append(f"Prov raw: {comprobante.proveedor_nombre_raw}")
    if observacion:
        obs_parts.append(observacion)
    observacion_full = " | ".join(obs_parts)

    factura = Factura(
        sucursal_id=sucursal_id,
        punto_venta=1,
        tipo=tipo,
        numero=numero,
        fecha=fecha_dt,
        cliente_id=None,
        cajero_id=user_id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=subtotal_total,
        total_iva=iva_total,
        total_descuento=Decimal("0"),
        total=total_total,
        moneda="ARS",
        cotizacion=Decimal("1"),
        observacion=observacion_full,
        legacy_meta={
            "origen": "ocr",
            "ocr_id": comprobante.id,
            "proveedor_id": proveedor_efectivo,
            "proveedor_nombre_raw": comprobante.proveedor_nombre_raw,
            "numero_proveedor": numero_override or comprobante.numero_comprobante,
        },
    )
    session.add(factura)
    session.flush()

    for r in items_resueltos:
        art: Articulo = r["articulo"]
        item = FacturaItem(
            factura_id=factura.id,
            articulo_id=art.id,
            codigo=art.codigo,
            descripcion=r["descripcion"] or art.descripcion,
            cantidad=r["cantidad"],
            precio_unitario=r["precio_unitario"],
            descuento_porc=r["descuento_porc"],
            iva_porc=r["iva_porc"],
            iva_monto=r["iva_monto"],
            subtotal=r["subtotal"],
            total=r["total"],
            orden=r["orden"],
        )
        session.add(item)

        # Stock: una compra suma stock.
        if art.controla_stock:
            stock_service.increment(session, art.id, sucursal_id, r["cantidad"])

    comprobante.estado = EstadoOcrEnum.confirmado
    comprobante.factura_creada_id = factura.id
    if proveedor_efectivo and comprobante.proveedor_id_match != proveedor_efectivo:
        comprobante.proveedor_id_match = proveedor_efectivo

    session.commit()
    return comprobante
