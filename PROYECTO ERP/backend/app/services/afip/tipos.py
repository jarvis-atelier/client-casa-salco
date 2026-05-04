"""Tablas de codigos AFIP — tipos de comprobante y condicion IVA del receptor.

Evitamos magic numbers en el resto del codigo. Todo mapping a codigos AFIP pasa por aqui.
"""
from __future__ import annotations

# Codigos AFIP para tipo de comprobante (WSFEv1).
# Fuente: https://www.afip.gob.ar/fe/documentos/TiposDeComprobantes.xlsx
TIPO_AFIP_MAP: dict[str, int] = {
    # Facturas
    "factura_a": 1,
    "factura_b": 6,
    "factura_c": 11,
    "factura_m": 51,
    # Notas de debito
    "nd_a": 2,
    "nd_b": 7,
    "nd_c": 12,
    "nd_m": 52,
    # Notas de credito
    "nc_a": 3,
    "nc_b": 8,
    "nc_c": 13,
    "nc_m": 53,
    # Recibos
    "recibo_a": 4,
    "recibo_b": 9,
    "recibo_c": 15,
    # Tickets (mismo codigo que Factura B/C en WSFEv1 — desambiguamos por receptor).
    "ticket": 6,  # por default usamos Factura B para CF; cambia a 11 si el emisor es monotributo.
    # FCE MiPyMEs (RG 4367).
    "fce_factura_a": 201,
    "fce_factura_b": 206,
    "fce_factura_c": 211,
    "fce_nd_a": 202,
    "fce_nd_b": 207,
    "fce_nd_c": 212,
    "fce_nc_a": 203,
    "fce_nc_b": 208,
    "fce_nc_c": 213,
}


# RG 5616 (Oct 2024): codigo de condicion IVA del receptor.
# Fuente: AFIP tabla sistema (FEParamGetCondicionIvaReceptor).
COND_IVA_RECEPTOR_RG_5616: dict[str, int] = {
    "responsable_inscripto": 1,
    "responsable_no_inscripto": 2,  # casi extinto
    "exento": 4,
    "consumidor_final": 5,
    "monotributo": 6,
    "sujeto_no_categorizado": 7,
    "proveedor_exterior": 8,
    "cliente_exterior": 9,
    "iva_liberado": 10,
    "iva_responsable_no_inscripto_agente_retencion": 13,
    "monotributo_social": 14,
    "no_categorizado": 15,  # default fallback
    "monotributista_trabajador_promovido": 16,
}


# Codigos de alicuota IVA AFIP (Id).
IVA_ALICUOTA_AFIP: dict[str, int] = {
    "0.00": 3,
    "10.50": 4,
    "21.00": 5,
    "27.00": 6,
    "5.00": 8,
    "2.50": 9,
}


def get_tipo_afip(key: str, default: int | None = None) -> int:
    """Lookup seguro — levanta KeyError si no hay mapping y no se paso default."""
    if key in TIPO_AFIP_MAP:
        return TIPO_AFIP_MAP[key]
    if default is not None:
        return default
    raise KeyError(f"Tipo AFIP desconocido: {key!r}")


def get_cond_iva_receptor(key: str, default: int | None = None) -> int:
    """Lookup para codigo condicion IVA receptor (RG 5616)."""
    if key in COND_IVA_RECEPTOR_RG_5616:
        return COND_IVA_RECEPTOR_RG_5616[key]
    if default is not None:
        return default
    raise KeyError(f"Condicion IVA receptor desconocida: {key!r}")
