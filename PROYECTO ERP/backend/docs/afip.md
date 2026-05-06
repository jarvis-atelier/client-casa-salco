# AFIP / ARCA — Guia de integracion

Fase 2.2 integra WSFEv1 de AFIP (facturacion electronica argentina) detras de una
interfaz limpia. En desarrollo usamos un `MockProvider` que NO llama a AFIP;
en produccion usamos `PyAfipWsProvider` (biblioteca `pyafipws` de Mariano Reingart).

## Modos de operacion

El selector es la variable de entorno `AFIP_MODE`:

| Modo        | Uso                                  | Requiere cert? | Requiere red? |
| ----------- | ------------------------------------ | -------------- | ------------- |
| `mock`      | Dev, tests, CI, demos                | No             | No            |
| `pyafipws`  | Produccion / homologacion            | Si             | Si            |
| `disabled`  | Tests que validan ausencia de AFIP   | No             | No            |

Si `AFIP_MODE=pyafipws` pero falta el cert o la libreria no esta instalada,
el factory cae automaticamente a `MockProvider` con un warning. Esto evita
que la app rompa en dev por error de config, pero si lo ves en prod: PELIGRO.

## Setup para produccion

### 1. Obtener el certificado AFIP

a. Cada CUIT emisor necesita su propio keypair.
b. Generar clave privada + CSR (Certificate Signing Request):

```bash
openssl genrsa -out privada.key 2048
openssl req -new -key privada.key -subj "/C=AR/O=MiEmpresa/CN=CASA SALCO/serialNumber=CUIT 20123456789" -out solicitud.csr
```

c. En el sitio de AFIP: **Administrador de Relaciones de Clave Fiscal**
   -> Adherir servicio -> elegir WSAA -> generar certificado con tu CSR.
   AFIP devuelve el `.crt`.

d. Copiar `certificado.crt` y `privada.key` al servidor:

```
backend/instance/afip_certs/<cuit>/certificado.crt
backend/instance/afip_certs/<cuit>/privada.key
```

### 2. Autorizar el servicio WSFE

En AFIP: **Administrador de Relaciones** -> Nueva relacion -> Servicio = `Facturacion
Electronica` (wsfe) -> asociar el certificado del paso 1.

### 3. Configurar el backend

En `.env` del backend:

```bash
AFIP_MODE=pyafipws
AFIP_HOMO=true            # true = testing AFIP, false = produccion real
AFIP_CUIT=20123456789
AFIP_CERT_PATH=instance/afip_certs/20123456789/certificado.crt
AFIP_KEY_PATH=instance/afip_certs/20123456789/privada.key
```

### 4. Instalar el extra `afip`

```bash
# Activar venv
.venv\Scripts\activate

# Instalar grupo opcional
pip install -e ".[afip]"
```

Esto trae: `pyafipws`, `lxml`, `cryptography`, `PyOpenSSL`, `qrcode[pil]`, `httpx`.

> **Nota Windows**: `pyafipws` puede ser tricky en Windows (depende de `lxml` y
> `PyOpenSSL` compilados). Si falla, consulta
> [pyafipws issues](https://github.com/PyAR/pyafipws/issues) o considera usar
> Linux/WSL para el entorno de produccion.

### 5. Homologacion (obligatorio antes de prod)

AFIP requiere pasar ~7 casos de prueba en homologacion antes de habilitar
produccion para un CUIT. Ver:

- https://www.afip.gob.ar/fe/documentos/manualdesarrolladorCOMPG_v4.pdf (protocolo)
- https://www.afip.gob.ar/fe/ayuda/informacionTecnica.asp (URLs)

Los casos tipicos: Factura A aprobada, Factura B aprobada, Factura con IVA 10.5%,
Nota de Credito con comprobante asociado, rechazo por CUIT invalido, etc.

Para activar produccion: `AFIP_HOMO=false` + haber registrado el cert contra el
ambiente de produccion AFIP (no solo homo).

## Arquitectura interna

```
app/services/afip/
  base.py              # FiscalInvoiceProvider (ABC), AfipFacturaInput/Output
  mock.py              # MockProvider — CAE deterministico sin red
  pyafipws_provider.py # PyAfipWsProvider — cliente WSFEv1 real
  factory.py           # get_provider() — selecciona segun AFIP_MODE
  qr.py                # generar_qr_url() segun spec AFIP
  tipos.py             # TIPO_AFIP_MAP, COND_IVA_RECEPTOR_RG_5616
```

## Endpoint HTTP

```
POST /api/v1/facturas/<id>/emitir-cae
Authorization: Bearer <jwt>
```

RBAC: solo `admin` y `supervisor`. Respuesta `201`:

```json
{
  "factura_id": 42,
  "cae": "73426521458291",
  "fecha_vencimiento": "2026-05-04",
  "numero_comprobante": 1,
  "punto_venta": 1,
  "tipo_afip": 6,
  "qr_url": "https://www.afip.gob.ar/fe/qr/?p=...",
  "proveedor": "mock",
  "resultado": "A",
  "reproceso": "N",
  "obs_afip": null
}
```

Errores:

- `404` — factura no encontrada
- `400 tipo_sin_cae` — remito/presupuesto no requieren CAE
- `409 cae_ya_emitido` — idempotencia (ya se emitio CAE antes)
- `422 afip_rejected` — AFIP devolvio resultado R
- `503 afip_unavailable` — no hay provider disponible
- `502 afip_error` — error de red o excepcion en pyafipws

## Auditoria regulatoria (RG 5409)

Cada CAE se persiste en la tabla `caes` con:

- `request_xml` / `response_xml` completos (para auditoria fiscal).
- `cuit_emisor`, `tipo_afip`, `punto_venta`, `numero` — la clave fiscal unica.
- `proveedor` — `"mock"` o `"pyafipws"` — para debug post-migracion.
- `qr_url` — URL AFIP del QR ya construida (no hace falta regenerarla en el ticket).

**Retencion minima 10 anios** por RG 5409. NO borrar esta tabla nunca.

## Bloqueadores conocidos para produccion

1. **Cert y key del cliente**: no se puede avanzar sin que el cliente provea su
   certificado AFIP. Cada CUIT tiene el suyo.
2. **Homologacion AFIP**: ~7 casos de prueba documentados arriba.
3. **Cacheo del TA (TicketAcceso)**: actualmente re-autenticamos por request.
   En prod, cachear a disco o Redis (el TA dura 12h). Optimizacion post-homo.
4. **QR en PDF**: `qr.py` tiene `generar_qr_png()` pero el flujo de impresion de
   la factura (PDF final) lo implementa la capa de templating, no este modulo.
