"""MockProvider — genera CAE deterministico para dev/test sin tocar AFIP.

Util para CI, desarrollo local, y demos. No requiere cert ni red. El CAE
que devuelve es numerico de 14 digitos pero NO es valido contra AFIP — es
solo un placeholder para que el flujo end-to-end funcione.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from .base import AfipFacturaInput, AfipFacturaOutput, FiscalInvoiceProvider


class MockProvider(FiscalInvoiceProvider):
    """Provider falso — NO usar en produccion."""

    name = "mock"

    # Contador interno para ultimo_autorizado() — por CUIT+tipo+pto_vta.
    # En tests multiples, el objeto se recrea por fixture asi que empieza en 0.
    _counters: dict[tuple[str, int, int], int]

    def __init__(self) -> None:
        self._counters = {}

    def solicitar_cae(self, data: AfipFacturaInput) -> AfipFacturaOutput:
        """Genera un CAE deterministico basado en los datos de entrada + timestamp.

        El CAE AFIP real tiene 14 digitos. Aqui usamos los primeros 14 digitos
        del hash hex para cumplir el formato. Incluimos el timestamp para que
        dos solicitudes consecutivas produzcan CAEs distintos (mejor UX en demos).
        """
        # Incrementamos el contador y usamos ese numero como "numero autorizado".
        key = (data.cuit_emisor, data.tipo_afip, data.punto_venta)
        self._counters[key] = self._counters.get(key, 0) + 1
        numero = self._counters[key]

        # Incluimos el numero en el seed para garantizar CAEs distintos aunque el
        # timestamp coincida en segundos (tests rapidos, bursts).
        seed = (
            f"{data.cuit_emisor}-{data.punto_venta}-{data.tipo_afip}-"
            f"{numero}-{datetime.utcnow().timestamp()}"
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        # Convertir los primeros 14 digitos hex a un int y truncar a 14 digitos decimal.
        cae_int = int(digest[:14], 16)
        cae = str(cae_int)[-14:].zfill(14)

        vencimiento = date.today() + timedelta(days=10)

        return AfipFacturaOutput(
            cae=cae,
            fecha_vencimiento=vencimiento,
            numero_comprobante=numero,
            resultado="A",
            reproceso="N",
            obs_afip=None,
            request_xml=None,
            response_xml=f"<mockResponse><cae>{cae}</cae></mockResponse>",
        )

    def ultimo_autorizado(self, cuit: str, tipo_afip: int, punto_venta: int) -> int:
        """En mock arrancamos en 0 — el proximo a emitir es 1."""
        return self._counters.get((cuit, tipo_afip, punto_venta), 0)
