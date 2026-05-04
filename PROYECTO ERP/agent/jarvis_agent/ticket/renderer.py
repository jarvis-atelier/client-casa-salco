"""Ticket renderer — pure functions that turn a Pydantic payload into:

- a list of plain-text lines (used by both PDF and ESC/POS to keep them in sync)
- raw ESC/POS bytes for thermal printers
- a QR PNG image (for the AFIP CAE QR)

The web POS does not need to know about ESC/POS at all. It just POSTs JSON.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import qrcode
from pydantic import BaseModel, ConfigDict, Field

from . import templates as T

# ----------------------------------------------------------------------------
# Pydantic schemas (request payload)
# ----------------------------------------------------------------------------


class Comercio(BaseModel):
    """Datos del comercio que emite (cabecera del ticket)."""

    razon_social: str
    cuit: str
    direccion: str | None = None
    telefono: str | None = None
    iibb: str | None = None
    inicio_actividades: str | None = None
    condicion_iva: str | None = None  # opcional para A/B/C


class SucursalPayload(BaseModel):
    codigo: str
    nombre: str
    punto_venta: int = 1


class ComprobantePayload(BaseModel):
    tipo_letra: str | None = None  # "A" | "B" | "C" | "X" - opcional
    numero: int
    fecha: datetime
    tipo_doc_receptor: int | None = None  # 80=CUIT, 86=CUIL, 96=DNI, 99=CF
    nro_doc_receptor: str | None = None
    razon_social_receptor: str | None = None
    condicion_iva_receptor: str | None = None


class ItemPayload(BaseModel):
    codigo: str
    descripcion: str
    cantidad: Decimal
    unidad: str | None = "unidad"
    precio_unitario: Decimal
    subtotal: Decimal
    iva_porc: Decimal | None = Decimal("21")
    descuento_porc: Decimal | None = Decimal("0")


class IvaDesglose(BaseModel):
    alic: Decimal  # 21, 10.5, 27, 5, 2.5, 0
    base: Decimal
    iva: Decimal


class TotalesPayload(BaseModel):
    subtotal: Decimal
    total_descuento: Decimal = Decimal("0")
    total_iva: Decimal = Decimal("0")
    iva_desglosado: list[IvaDesglose] = Field(default_factory=list)
    total: Decimal


class PagoPayload(BaseModel):
    medio: str
    monto: Decimal
    referencia: str | None = None


class AfipPayload(BaseModel):
    cae: str
    vencimiento: date | str
    qr_url: str


TipoComprobante = Literal[
    "ticket",
    "factura_a",
    "factura_b",
    "factura_c",
    "nc_a",
    "nc_b",
    "nc_c",
    "remito",
    "presupuesto",
    "comanda",
]


class TicketPayload(BaseModel):
    """Full ticket payload accepted by /print/ticket."""

    model_config = ConfigDict(extra="ignore")

    tipo: TipoComprobante = "ticket"
    comercio: Comercio
    sucursal: SucursalPayload
    comprobante: ComprobantePayload
    items: list[ItemPayload]
    totales: TotalesPayload
    pagos: list[PagoPayload] = Field(default_factory=list)
    afip: AfipPayload | None = None
    cajero: str | None = None
    observacion: str | None = None
    ancho_papel_mm: int = 80


# ----------------------------------------------------------------------------
# Result dataclass
# ----------------------------------------------------------------------------


@dataclass
class RenderedTicket:
    """Output of `render_ticket()` — used by all printer drivers."""

    payload: TicketPayload
    width_chars: int
    lines: list[str]                  # plain-text lines for PDF/log
    escpos_bytes: bytes               # bytes ready to send to USB / Network
    qr_png: bytes | None = None       # AFIP QR (PNG) — already embedded in escpos_bytes
    metadata: dict[str, str] = field(default_factory=dict)


# ----------------------------------------------------------------------------
# QR helper
# ----------------------------------------------------------------------------


def make_qr_png(url: str, *, size_px: int = 192) -> bytes:
    """Render the AFIP QR URL as a PNG image (square)."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    # Force a target size for stable layout in PDF
    img = img.resize((size_px, size_px))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Plain-text line builder (shared by PDF + ESC/POS)
# ----------------------------------------------------------------------------


def _build_text_lines(p: TicketPayload, width: int) -> list[str]:
    """Render the ticket as a list of plain-text lines.

    The ESC/POS encoder will overlay typography (bold/double-height) on top of
    these lines using semantic markers, but the `lines` list itself stays plain
    so the PDF mock renderer can use it verbatim.
    """
    lines: list[str] = []

    # === HEADER ============================================================
    lines.append(T.center(p.comercio.razon_social.upper(), width))
    lines.append(T.center(f"{p.sucursal.nombre} - {p.sucursal.codigo}", width))
    if p.comercio.direccion:
        lines.append(T.center(p.comercio.direccion, width))
    cuit_line = f"CUIT: {p.comercio.cuit}"
    if p.comercio.iibb:
        cuit_line += f"   IIBB: {p.comercio.iibb}"
    lines.append(T.center(cuit_line, width))
    if p.comercio.condicion_iva:
        lines.append(T.center(p.comercio.condicion_iva, width))
    if p.comercio.inicio_actividades:
        lines.append(T.center(f"Inicio Act.: {p.comercio.inicio_actividades}", width))
    lines.append("")

    # === COMPROBANTE TYPE BANNER ==========================================
    banner = T.header_label(p.tipo, p.comprobante.tipo_letra)
    lines.append(T.center(banner, width))
    nro_str = (
        f"{p.sucursal.punto_venta:04d}-{p.comprobante.numero:08d}"
        if p.tipo != "comanda"
        else f"#{p.comprobante.numero}"
    )
    lines.append(T.center(nro_str, width))
    lines.append("")

    # === META ==============================================================
    fecha_str = p.comprobante.fecha.strftime("%d/%m/%Y %H:%M")
    lines.append(T.kv_line("Fecha:", fecha_str, width))
    if p.cajero:
        lines.append(T.kv_line("Cajero:", p.cajero, width))
    if p.comprobante.razon_social_receptor:
        lines.append(T.kv_line("Cliente:", p.comprobante.razon_social_receptor, width))
    if p.comprobante.nro_doc_receptor and p.comprobante.nro_doc_receptor != "0":
        doc_label = "CUIT" if p.comprobante.tipo_doc_receptor in (80, 86) else "Doc"
        lines.append(T.kv_line(f"{doc_label}:", p.comprobante.nro_doc_receptor, width))
    if p.comprobante.condicion_iva_receptor:
        lines.append(T.kv_line("Cond.IVA:", p.comprobante.condicion_iva_receptor, width))

    lines.append(T.hr(width))

    # === ITEMS =============================================================
    if p.tipo != "comanda":
        lines.append(T.two_cols("ARTICULO", "IMPORTE", width))
        lines.append(T.hr(width))

    for it in p.items:
        # First line: description (wrapped)
        for chunk in T.wrap(it.descripcion, width):
            lines.append(chunk)

        if p.tipo == "comanda":
            # Comanda: only qty + unit, no price
            qty_unit = T.fmt_qty(it.cantidad, it.unidad)
            lines.append(f"  {qty_unit}".ljust(width))
            continue

        # Pricing line
        qty_str = T.fmt_qty(it.cantidad, it.unidad)
        unit_str = T.fmt_money(it.precio_unitario)
        left = f"  {qty_str} x {unit_str}".rstrip()
        right = T.fmt_money(it.subtotal)
        lines.append(T.two_cols(left, right, width))

    lines.append(T.hr(width))

    # === TOTALES ===========================================================
    if p.tipo != "comanda":
        lines.append(T.two_cols("Subtotal", T.fmt_money(p.totales.subtotal), width))

        if p.totales.total_descuento and p.totales.total_descuento != Decimal("0"):
            lines.append(
                T.two_cols(
                    "Descuento", "-" + T.fmt_money(p.totales.total_descuento), width
                )
            )

        for d in p.totales.iva_desglosado:
            label = f"IVA {d.alic:.1f}%".replace(".0%", "%")
            lines.append(T.two_cols(label, T.fmt_money(d.iva), width))

        lines.append(T.hr(width))
        # TOTAL — ESC/POS will render this in double size; PDF will use bigger font
        lines.append(T.two_cols("TOTAL", T.fmt_money(p.totales.total), width))
        lines.append(T.hr(width))

        # === PAGOS ==========================================================
        if p.pagos:
            for pago in p.pagos:
                etiqueta = pago.medio.replace("_", " ").capitalize()
                lines.append(T.two_cols(etiqueta, T.fmt_money(pago.monto), width))
            lines.append(T.hr(width))

    # === AFIP / CAE ========================================================
    if p.afip:
        lines.append(f"CAE: {p.afip.cae}")
        venc = (
            p.afip.vencimiento.strftime("%d/%m/%Y")
            if isinstance(p.afip.vencimiento, date)
            else str(p.afip.vencimiento)
        )
        lines.append(f"Vto CAE: {venc}")
        lines.append("[QR AFIP]")  # marker — PDF/ESC encoder render the actual QR here

    # === FOOTER ============================================================
    if p.observacion:
        lines.append("")
        for chunk in T.wrap(f"Obs: {p.observacion}", width):
            lines.append(chunk)

    lines.append("")
    lines.append(T.center("Gracias por su compra", width))
    lines.append(T.center("Jarvis Core", width))

    return lines


# ----------------------------------------------------------------------------
# ESC/POS encoder (mostly raw — we don't depend on python-escpos for bytes,
# only for the actual transport in `printer/escpos_*.py`).
# ----------------------------------------------------------------------------

# ESC/POS control codes -------------------------------------------------------
ESC = b"\x1b"
GS = b"\x1d"
LF = b"\n"

INIT = ESC + b"@"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
DOUBLE_HW = GS + b"!\x11"  # double width + double height
NORMAL_SIZE = GS + b"!\x00"
CUT_PARTIAL = GS + b"V\x42\x00"


def _encode_text(s: str) -> bytes:
    """Encode a text line for the printer.

    3NSTAR PRP-080 supports CP858 / CP437 by default. We strip / fallback for
    Argentine Spanish punctuation. UTF-8 is rejected by most ESC/POS printers.
    """
    table = str.maketrans(
        {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "Á": "A",
            "É": "E",
            "Í": "I",
            "Ó": "O",
            "Ú": "U",
            "ñ": "n",
            "Ñ": "N",
            "ü": "u",
            "Ü": "U",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
            "—": "-",
            "–": "-",
            "·": "-",
            "°": "o",
        }
    )
    safe = s.translate(table)
    return safe.encode("cp437", errors="replace")


def _qr_image_to_escpos(png_bytes: bytes, *, max_width: int = 384) -> bytes:
    """Convert a PNG to an ESC/POS GS v 0 raster image.

    Many ESC/POS printers support raster images via `GS v 0`. This is portable
    and avoids depending on the QR-code firmware feature.
    """
    from PIL import Image  # local import; Pillow already required

    img = Image.open(io.BytesIO(png_bytes)).convert("1")
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((max_width, int(h * ratio)))
        w, h = img.size

    width_bytes = (w + 7) // 8
    raster = bytearray()
    pixels = img.load()
    if pixels is None:
        return b""
    for y in range(h):
        for xb in range(width_bytes):
            byte = 0
            for bit in range(8):
                x = xb * 8 + bit
                if x < w and pixels[x, y] == 0:  # black pixel
                    byte |= 1 << (7 - bit)
            raster.append(byte)

    out = bytearray()
    out += GS + b"v0\x00"
    out += bytes([width_bytes & 0xFF, (width_bytes >> 8) & 0xFF])
    out += bytes([h & 0xFF, (h >> 8) & 0xFF])
    out += bytes(raster)
    out += LF
    return bytes(out)


def _build_escpos(p: TicketPayload, lines: list[str], qr_png: bytes | None) -> bytes:
    """Encode ticket lines as ESC/POS bytes — applies bold to header, double
    size to TOTAL, embeds QR.
    """
    out = bytearray()
    out += INIT

    # Find anchor lines that should get special typography
    razon_social = p.comercio.razon_social.upper()
    banner = T.header_label(p.tipo, p.comprobante.tipo_letra)
    qr_marker = "[QR AFIP]"

    for line in lines:
        stripped = line.strip()

        if stripped == qr_marker:
            if qr_png:
                out += ALIGN_CENTER
                out += _qr_image_to_escpos(qr_png)
                out += ALIGN_LEFT
            continue

        if razon_social in line.upper():
            out += ALIGN_CENTER + BOLD_ON + DOUBLE_HW
            out += _encode_text(line.strip())
            out += LF + NORMAL_SIZE + BOLD_OFF + ALIGN_LEFT
            continue

        if banner in line:
            out += ALIGN_CENTER + BOLD_ON + DOUBLE_HW
            out += _encode_text(line.strip())
            out += LF + NORMAL_SIZE + BOLD_OFF + ALIGN_LEFT
            continue

        if line.lstrip().startswith("TOTAL") and "$" in line:
            out += BOLD_ON + DOUBLE_HW
            out += _encode_text(line)
            out += LF + NORMAL_SIZE + BOLD_OFF
            continue

        out += _encode_text(line)
        out += LF

    out += LF + LF + LF
    out += CUT_PARTIAL
    return bytes(out)


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------


def render_ticket(payload: TicketPayload) -> RenderedTicket:
    """Render a TicketPayload into all output formats."""
    width = T.width_for_paper_mm(payload.ancho_papel_mm)
    lines = _build_text_lines(payload, width)

    qr_png: bytes | None = None
    if payload.afip and payload.afip.qr_url:
        qr_png = make_qr_png(payload.afip.qr_url)

    escpos = _build_escpos(payload, lines, qr_png)

    nro_str = (
        f"{payload.sucursal.punto_venta:04d}-{payload.comprobante.numero:08d}"
    )
    metadata = {
        "tipo": payload.tipo,
        "numero": nro_str,
        "fecha_iso": payload.comprobante.fecha.isoformat(),
        "total": str(payload.totales.total),
        "ancho_chars": str(width),
    }

    return RenderedTicket(
        payload=payload,
        width_chars=width,
        lines=lines,
        escpos_bytes=escpos,
        qr_png=qr_png,
        metadata=metadata,
    )
