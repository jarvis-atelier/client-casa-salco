"""PyAfipWsProvider — cliente real WSFEv1 via la biblioteca `pyafipws` de Mariano Reingart.

Esta es la implementacion para PRODUCCION. Requiere:

1. Grupo opcional instalado: `pip install -e ".[afip]"` (pyafipws + lxml + cryptography + PyOpenSSL)
2. Certificado AFIP + clave privada (ver `backend/docs/afip.md`)
3. CUIT del emisor registrado en AFIP contra el cert

Notas tecnicas:
- WSAA: Web Service de Autenticacion y Autorizacion. Firma un TRA (Ticket Requerimiento de
  Acceso) con el cert, lo envia a AFIP, recibe un TA (Ticket de Acceso) con tokens.
- WSFEv1: Web Service de Facturacion Electronica v1. Consume el TA y emite CAE.
- Ambos viajan sobre HTTPS+SOAP. pyafipws encapsula todo.
- En Windows, la instalacion de pyafipws es tricky (depende de lxml/pyOpenSSL compilados).
  Si falla, el factory cae automaticamente a MockProvider con un warning (en dev).
- Homologacion: AFIP exige pasar ~7 casos de prueba antes de habilitar produccion. Ver
  `backend/docs/afip.md` y https://www.afip.gob.ar/fe/documentos/
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from .base import (
    AfipFacturaInput,
    AfipFacturaOutput,
    FiscalInvoiceProvider,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

# URLs oficiales AFIP — ver https://www.afip.gob.ar/fe/ayuda/informacionTecnica.asp
WSAA_WSDL_HOMO = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
WSAA_WSDL_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
WSFEV1_WSDL_HOMO = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
WSFEV1_WSDL_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"


def _lazy_import_pyafipws() -> tuple:
    """Importa pyafipws solo cuando hace falta. Si falta, lanza ProviderUnavailableError."""
    try:
        from pyafipws.wsaa import WSAA  # type: ignore
        from pyafipws.wsfev1 import WSFEv1  # type: ignore

        return WSAA, WSFEv1
    except ImportError as err:  # pragma: no cover — depende del entorno
        raise ProviderUnavailableError(
            "pyafipws no esta instalado. Activalo con: "
            'pip install -e ".[afip]"  (puede fallar en Windows — '
            "ver backend/docs/afip.md)"
        ) from err


class PyAfipWsProvider(FiscalInvoiceProvider):
    """Provider real que habla WSFEv1 contra AFIP via pyafipws."""

    name = "pyafipws"

    def __init__(
        self,
        cuit: str,
        cert_path: str | None,
        key_path: str | None,
        homo: bool = True,
    ) -> None:
        if not cert_path or not key_path:
            raise ProviderUnavailableError(
                "PyAfipWsProvider requiere AFIP_CERT_PATH y AFIP_KEY_PATH. "
                "Ver backend/docs/afip.md para obtener cert de AFIP."
            )
        cert = Path(cert_path)
        key = Path(key_path)
        if not cert.is_file():
            raise ProviderUnavailableError(f"Cert AFIP no encontrado: {cert_path}")
        if not key.is_file():
            raise ProviderUnavailableError(f"Key AFIP no encontrada: {key_path}")

        # Verificamos que pyafipws este instalado ANTES de hacer red.
        self._WSAA, self._WSFEv1 = _lazy_import_pyafipws()

        self.cuit = "".join(ch for ch in cuit if ch.isdigit())
        self.cert_path = str(cert)
        self.key_path = str(key)
        self.homo = homo

        self._wsaa = None
        self._wsfe = None
        self._ta_xml: str | None = None

    # ------------------------------------------------------------------ auth

    def _authenticate(self) -> None:
        """Crea/renueva el Ticket de Acceso (TA) contra WSAA.

        El TA tiene validez de 12 horas. En esta implementacion pedimos uno
        por request; en una optimizacion futura cachear a disco o Redis.
        """
        wsaa = self._WSAA()
        wsdl = WSAA_WSDL_HOMO if self.homo else WSAA_WSDL_PROD
        ta_xml = wsaa.Autenticar(
            "wsfe",  # service name
            self.cert_path,
            self.key_path,
            wsdl,
            "",
            "",
            "",
            True,  # cache
            False,  # debug
        )
        if not ta_xml:
            raise ProviderUnavailableError(
                f"WSAA auth fallo: {getattr(wsaa, 'Excepcion', '')} / "
                f"{getattr(wsaa, 'Traceback', '')}"
            )
        self._ta_xml = ta_xml
        self._wsaa = wsaa

    def _get_wsfe(self):
        """Inicializa WSFEv1 con el TA actual (re-autentica si hace falta)."""
        if self._ta_xml is None:
            self._authenticate()
        if self._wsfe is not None:
            return self._wsfe

        wsfe = self._WSFEv1()
        wsfe.SetTicketAcceso(self._ta_xml)
        wsfe.Cuit = self.cuit
        wsdl = WSFEV1_WSDL_HOMO if self.homo else WSFEV1_WSDL_PROD
        wsfe.Conectar("", wsdl)
        self._wsfe = wsfe
        return wsfe

    # ----------------------------------------------------------- operations

    def ultimo_autorizado(self, cuit: str, tipo_afip: int, punto_venta: int) -> int:
        wsfe = self._get_wsfe()
        # CompUltimoAutorizado retorna el ultimo numero autorizado por AFIP para
        # el combo (tipo, pto_vta). El proximo a emitir es este + 1.
        numero = wsfe.CompUltimoAutorizado(tipo_afip, punto_venta)
        try:
            return int(numero or 0)
        except (TypeError, ValueError):
            return 0

    def solicitar_cae(self, data: AfipFacturaInput) -> AfipFacturaOutput:
        wsfe = self._get_wsfe()

        # 1) Determinar el proximo numero de comprobante.
        ultimo = self.ultimo_autorizado(
            data.cuit_emisor, data.tipo_afip, data.punto_venta
        )
        numero = ultimo + 1

        # 2) Armar la factura (CrearFactura segun API nueva ARCA FEAFIP).
        fecha_cbte = data.fecha_comprobante.strftime("%Y%m%d")
        wsfe.CrearFactura(
            concepto=data.concepto,
            tipo_doc=data.tipo_doc_receptor,
            nro_doc=data.nro_doc_receptor,
            tipo_cbte=data.tipo_afip,
            punto_vta=data.punto_venta,
            cbt_desde=numero,
            cbt_hasta=numero,
            imp_total=float(data.importe_total),
            imp_tot_conc=float(data.importe_tot_conc),
            imp_neto=float(data.importe_neto),
            imp_iva=float(data.importe_iva),
            imp_trib=float(data.importe_trib),
            imp_op_ex=float(data.importe_op_ex),
            fecha_cbte=fecha_cbte,
            fecha_venc_pago=None,
            fecha_serv_desde=None,
            fecha_serv_hasta=None,
            moneda_id=data.moneda,
            moneda_ctz=float(data.cotizacion),
        )

        # RG 5616 — CondicionIVAReceptorId obligatorio en Factura A y muchos B/C.
        if data.cond_iva_receptor_id is not None:
            try:
                wsfe.EstablecerCampoFactura(
                    "condicion_iva_receptor_id", data.cond_iva_receptor_id
                )
            except Exception as exc:  # pragma: no cover — compatibilidad versiones
                logger.warning("EstablecerCampoFactura fallo: %s", exc)

        # 3) Agregar items de IVA por alicuota.
        for item in data.items_iva:
            wsfe.AgregarIva(
                iva_id=int(item["alic"]),
                base_imp=float(item["base"]),
                importe=float(item["iva"]),
            )

        # 4) Solicitar CAE.
        cae = wsfe.CAESolicitar()

        resultado = getattr(wsfe, "Resultado", "") or ""
        obs = getattr(wsfe, "Obs", "") or ""
        reproceso = getattr(wsfe, "Reproceso", "") or "N"
        vto_str = getattr(wsfe, "Vencimiento", "") or ""
        xml_req = getattr(wsfe, "XmlRequest", None)
        xml_res = getattr(wsfe, "XmlResponse", None)

        try:
            vencimiento = datetime.strptime(vto_str, "%Y%m%d").date() if vto_str else date.today()
        except ValueError:
            vencimiento = date.today()

        return AfipFacturaOutput(
            cae=str(cae or "").zfill(14) if resultado == "A" else "",
            fecha_vencimiento=vencimiento,
            numero_comprobante=numero,
            resultado=resultado or "R",
            reproceso=reproceso,
            obs_afip=obs or None,
            request_xml=xml_req,
            response_xml=xml_res,
        )
