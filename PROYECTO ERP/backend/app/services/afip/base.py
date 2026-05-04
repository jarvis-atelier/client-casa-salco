"""Interfaz abstracta del provider de facturacion electronica AFIP.

Esta es la abstraccion clave de Fase 2.2: el resto del codigo solo conoce
`FiscalInvoiceProvider`. El mock y el PyAfipWs real implementan esta interfaz.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


class ProviderUnavailableError(RuntimeError):
    """Lanzada cuando el provider no puede instanciarse (dependencia faltante,
    cert invalido, sin red, etc.). El factory puede caer a mock en dev."""


@dataclass
class AfipFacturaInput:
    """Datos de entrada para solicitar un CAE a AFIP.

    Mapea conceptualmente al request FECAERequest de WSFEv1.
    """

    cuit_emisor: str
    tipo_afip: int  # codigo AFIP (1=FactA, 6=FactB, 11=FactC, etc.)
    punto_venta: int
    concepto: int  # 1=productos, 2=servicios, 3=ambos
    tipo_doc_receptor: int  # 80=CUIT, 86=CUIL, 96=DNI, 99=Consumidor Final
    nro_doc_receptor: str
    # RG 5616 (Oct 2024): obligatorio en Facturas A y en muchos casos B/C.
    cond_iva_receptor_id: int | None
    fecha_comprobante: date
    importe_neto: Decimal
    importe_iva: Decimal
    importe_total: Decimal
    # Items de IVA por alicuota. Cada dict: {"alic": <cod_afip>, "base": Decimal, "iva": Decimal}
    # Codigos AFIP alicuota: 3=0%, 4=10.5%, 5=21%, 6=27%, 8=5%, 9=2.5%.
    items_iva: list[dict] = field(default_factory=list)
    importe_trib: Decimal = Decimal("0")
    importe_tot_conc: Decimal = Decimal("0")  # neto no gravado
    importe_op_ex: Decimal = Decimal("0")  # exento
    moneda: str = "PES"
    cotizacion: Decimal = Decimal("1")
    observaciones: str | None = None


@dataclass
class AfipFacturaOutput:
    """Resultado de la solicitud a AFIP.

    Si `resultado == "R"`, `cae` puede estar vacio. El caller debe
    chequear `resultado` antes de asumir emision exitosa.
    """

    cae: str
    fecha_vencimiento: date
    numero_comprobante: int
    resultado: str  # A=Aprobado, R=Rechazado, P=Parcial, X=Observado
    reproceso: str  # S=Si (reintento) / N=No
    obs_afip: str | None = None
    request_xml: str | None = None
    response_xml: str | None = None


class FiscalInvoiceProvider(ABC):
    """Interfaz que todo provider (mock, pyafipws, futuro adaptador HTTP) debe cumplir."""

    @abstractmethod
    def solicitar_cae(self, data: AfipFacturaInput) -> AfipFacturaOutput:
        """Pide un CAE a AFIP (o lo simula). Retorna `AfipFacturaOutput` aun en caso
        de rechazo (con `resultado="R"` y `obs_afip` con el detalle)."""

    @abstractmethod
    def ultimo_autorizado(self, cuit: str, tipo_afip: int, punto_venta: int) -> int:
        """Retorna el ultimo numero de comprobante autorizado por AFIP para el
        combo (cuit, tipo, pto_vta). El siguiente a emitir es este + 1.

        Usado para seed de la numeracion al arrancar el sistema (evita gaps
        que AFIP solo permite si se declaran formalmente).
        """
