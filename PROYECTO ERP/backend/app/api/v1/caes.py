"""Endpoints de emision de CAE — Fase 2.2.

Expone `POST /api/v1/facturas/<id>/emitir-cae` para pedir un CAE a AFIP (o al mock
en dev) para una factura ya existente. Actualiza la Factura con el CAE/vencimiento
y persiste el detalle en el modelo Cae (audit log regulatorio RG 5409).

Idempotencia: si la factura ya tiene un Cae asociado, responde 409 en lugar de pedir
otro. NO es posible emitir dos CAEs para la misma factura — es una restriccion AFIP.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from flask import Blueprint, jsonify

from app.extensions import db
from app.models.cae import Cae
from app.models.cliente import CondicionIvaEnum
from app.models.factura import Factura, TipoComprobanteEnum
from app.services.afip import (
    AfipFacturaInput,
    ProviderUnavailableError,
    generar_qr_url,
    get_provider,
)
from app.services.afip.tipos import (
    COND_IVA_RECEPTOR_RG_5616,
    TIPO_AFIP_MAP,
)
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

logger = logging.getLogger(__name__)

bp = Blueprint("caes", __name__, url_prefix="/api/v1/facturas")


# Mapeo del enum interno TipoComprobanteEnum al codigo AFIP (o a la key del TIPO_AFIP_MAP).
TIPO_COMPROBANTE_TO_AFIP_KEY: dict[str, str] = {
    TipoComprobanteEnum.factura_a.value: "factura_a",
    TipoComprobanteEnum.factura_b.value: "factura_b",
    TipoComprobanteEnum.factura_c.value: "factura_c",
    TipoComprobanteEnum.ticket.value: "ticket",
    TipoComprobanteEnum.nota_credito_a.value: "nc_a",
    TipoComprobanteEnum.nota_credito_b.value: "nc_b",
    TipoComprobanteEnum.nota_credito_c.value: "nc_c",
}


# Tipos que NO requieren CAE (remito interno, presupuesto).
TIPOS_SIN_CAE: set[str] = {
    TipoComprobanteEnum.remito.value,
    TipoComprobanteEnum.presupuesto.value,
}


@bp.post("/<int:factura_id>/emitir-cae")
@roles_required("admin", "supervisor")
def emitir_cae(factura_id: int):
    factura: Factura | None = db.session.get(Factura, factura_id)
    if factura is None:
        return error_response("factura no encontrada", 404, "not_found")

    # Chequear tipo: no pedimos CAE a AFIP por remitos/presupuestos.
    if factura.tipo.value in TIPOS_SIN_CAE:
        return error_response(
            f"tipo {factura.tipo.value!r} no requiere CAE",
            400,
            "tipo_sin_cae",
        )

    # Idempotencia: un solo CAE por factura.
    existing: Cae | None = (
        db.session.query(Cae).filter(Cae.factura_id == factura.id).first()
    )
    if existing is not None:
        return error_response(
            f"factura ya tiene CAE emitido ({existing.cae})",
            409,
            "cae_ya_emitido",
            details={
                "cae": existing.cae,
                "fecha_vencimiento": existing.fecha_vencimiento.isoformat(),
                "proveedor": existing.proveedor,
            },
        )

    # Armar input AFIP desde la Factura.
    try:
        afip_input = _build_afip_input(factura)
    except ValueError as err:
        return error_response(str(err), 422, "invalid_factura_for_cae")

    # Solicitar CAE al provider configurado.
    try:
        provider = get_provider()
    except (RuntimeError, ProviderUnavailableError) as exc:
        logger.exception("No se pudo obtener provider AFIP: %s", exc)
        return error_response(
            f"provider AFIP no disponible: {exc}", 503, "afip_unavailable"
        )

    try:
        output = provider.solicitar_cae(afip_input)
    except Exception as exc:  # pragma: no cover — defensivo contra fallos de red/AFIP
        logger.exception("Fallo en solicitar_cae: %s", exc)
        return error_response(
            f"error solicitando CAE: {exc}", 502, "afip_error"
        )

    if output.resultado != "A":
        # AFIP rechazo — NO guardamos el Cae porque no tenemos numero valido.
        # Pero logueamos y devolvemos 422 con el detalle.
        logger.warning(
            "AFIP rechazo CAE factura_id=%s resultado=%s obs=%s",
            factura.id,
            output.resultado,
            output.obs_afip,
        )
        return error_response(
            "AFIP rechazo la emision de CAE",
            422,
            "afip_rejected",
            details={
                "resultado": output.resultado,
                "observaciones": output.obs_afip,
            },
        )

    # Construir URL del QR AFIP.
    cuit_clean = "".join(ch for ch in afip_input.cuit_emisor if ch.isdigit())
    qr_url = generar_qr_url(
        cuit=cuit_clean,
        pto_vta=afip_input.punto_venta,
        tipo_cmp=afip_input.tipo_afip,
        nro_cmp=output.numero_comprobante,
        importe=afip_input.importe_total,
        cae=output.cae,
        fecha=afip_input.fecha_comprobante,
        tipo_doc_rec=afip_input.tipo_doc_receptor,
        nro_doc_rec=afip_input.nro_doc_receptor,
        moneda=afip_input.moneda,
        cotizacion=afip_input.cotizacion,
    )

    # Persistir Cae + actualizar Factura.
    cae = Cae(
        factura_id=factura.id,
        cuit_emisor=cuit_clean,
        tipo_afip=afip_input.tipo_afip,
        punto_venta=afip_input.punto_venta,
        numero=output.numero_comprobante,
        cae=output.cae,
        fecha_vencimiento=output.fecha_vencimiento,
        fecha_emision=datetime.now(UTC),
        proveedor=getattr(provider, "name", "unknown"),
        request_xml=output.request_xml,
        response_xml=output.response_xml,
        qr_url=qr_url,
        obs_afip=output.obs_afip,
        resultado=output.resultado,
        reproceso=output.reproceso,
    )
    factura.cae = output.cae
    factura.cae_vencimiento = output.fecha_vencimiento
    factura.qr_afip = qr_url

    db.session.add(cae)
    db.session.commit()

    return (
        jsonify(
            {
                "factura_id": factura.id,
                "cae": output.cae,
                "fecha_vencimiento": output.fecha_vencimiento.isoformat(),
                "numero_comprobante": output.numero_comprobante,
                "punto_venta": afip_input.punto_venta,
                "tipo_afip": afip_input.tipo_afip,
                "qr_url": qr_url,
                "proveedor": cae.proveedor,
                "resultado": output.resultado,
                "reproceso": output.reproceso,
                "obs_afip": output.obs_afip,
            }
        ),
        201,
    )


def _build_afip_input(factura: Factura) -> AfipFacturaInput:
    """Arma el dataclass AfipFacturaInput desde una Factura + su cliente.

    Maneja:
    - Mapeo tipo_comprobante_enum -> codigo AFIP.
    - Concepto (1=productos por default; se podria inferir de items mas fino).
    - Receptor: si es CF anonimo (sin cliente_id), tipo_doc=99, nro_doc=0.
    - RG 5616: condicion_iva_receptor_id mandatory para tipos A y recomendado
      en B/C cuando conocemos al cliente.
    """
    from app.config import get_settings

    settings = get_settings()

    # Codigo AFIP del tipo de comprobante.
    tipo_key = TIPO_COMPROBANTE_TO_AFIP_KEY.get(factura.tipo.value)
    if tipo_key is None:
        raise ValueError(f"tipo de comprobante sin mapping AFIP: {factura.tipo.value}")
    tipo_afip = TIPO_AFIP_MAP[tipo_key]

    # Receptor.
    cliente = factura.cliente
    if cliente is None:
        # Consumidor Final anonimo — tipo_doc=99, nro_doc=0.
        tipo_doc = 99
        nro_doc = "0"
        cond_iva_rec_id = COND_IVA_RECEPTOR_RG_5616["consumidor_final"]
    else:
        if cliente.cuit:
            tipo_doc = 80  # CUIT
            nro_doc = cliente.cuit
        else:
            tipo_doc = 99  # CF sin CUIT
            nro_doc = "0"
        # Prioridad: campo explicito del cliente -> derivar de condicion_iva.
        if cliente.condicion_iva_receptor_id is not None:
            cond_iva_rec_id = cliente.condicion_iva_receptor_id
        else:
            cond_iva_rec_id = _derivar_cond_iva_receptor(cliente.condicion_iva)

    # IVA por alicuota — asumimos 21% por default si no hay desglose.
    # (Fase 2.1 / el POS armara items_iva fino a partir de los FacturaItem.)
    items_iva: list[dict] = []
    if factura.total_iva and factura.total_iva > 0:
        base_21 = (factura.subtotal or Decimal("0")) - (factura.total_descuento or Decimal("0"))
        items_iva.append(
            {
                "alic": 5,  # 21%
                "base": base_21,
                "iva": factura.total_iva,
            }
        )

    # Neto = total - iva (aproximado; ajustable segun items_iva real).
    importe_neto = (factura.total or Decimal("0")) - (factura.total_iva or Decimal("0"))

    return AfipFacturaInput(
        cuit_emisor=settings.AFIP_CUIT,
        tipo_afip=tipo_afip,
        punto_venta=factura.punto_venta,
        concepto=1,  # productos por default; refinar cuando POS distinga servicios.
        tipo_doc_receptor=tipo_doc,
        nro_doc_receptor=nro_doc,
        cond_iva_receptor_id=cond_iva_rec_id,
        fecha_comprobante=factura.fecha.date() if factura.fecha else datetime.now(UTC).date(),
        importe_neto=importe_neto,
        importe_iva=factura.total_iva or Decimal("0"),
        importe_total=factura.total or Decimal("0"),
        items_iva=items_iva,
        moneda="PES" if (factura.moneda or "ARS").upper() in ("ARS", "PES") else factura.moneda,
        cotizacion=factura.cotizacion or Decimal("1"),
        observaciones=factura.observacion,
    )


def _derivar_cond_iva_receptor(cond: CondicionIvaEnum) -> int:
    """Mapea el enum interno `CondicionIvaEnum` al codigo AFIP RG 5616."""
    mapping = {
        CondicionIvaEnum.responsable_inscripto: COND_IVA_RECEPTOR_RG_5616[
            "responsable_inscripto"
        ],
        CondicionIvaEnum.monotributo: COND_IVA_RECEPTOR_RG_5616["monotributo"],
        CondicionIvaEnum.consumidor_final: COND_IVA_RECEPTOR_RG_5616["consumidor_final"],
        CondicionIvaEnum.exento: COND_IVA_RECEPTOR_RG_5616["exento"],
        CondicionIvaEnum.no_categorizado: COND_IVA_RECEPTOR_RG_5616["no_categorizado"],
    }
    return mapping.get(cond, COND_IVA_RECEPTOR_RG_5616["no_categorizado"])
