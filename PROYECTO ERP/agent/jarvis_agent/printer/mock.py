"""Mock printer — generates a PDF preview that mirrors the real ESC/POS layout.

This driver lets the POS frontend test the full print flow without a physical
3NSTAR printer connected. It produces:

- A PDF in `{OUTPUT_DIR}/{timestamp}-{numero}.pdf` (returned via `/preview/<id>`)
- A `.txt` dump alongside it (raw plain-text lines — handy for diffing tickets)
- Console log of the rendered text

The PDF size mimics 80 mm thermal paper (~80mm wide x dynamic height).
"""
from __future__ import annotations

import io
import logging
import time
from datetime import datetime
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ..config import get_settings
from ..ticket.renderer import RenderedTicket
from .base import IPrinterDriver, PrintResult, PrinterStatus

log = logging.getLogger(__name__)


class MockPrinter(IPrinterDriver):
    """Generates a PDF preview instead of printing on hardware."""

    name = "mock"

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or get_settings().output_dir_path
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._last_id: str | None = None

    # ------------------------------------------------------------------
    def status(self) -> PrinterStatus:  # noqa: D401
        """Always reports ready — useful for dev."""
        return PrinterStatus(
            status="ready",
            driver="mock",
            model="mock-pdf",
            papel="ok",
            online=True,
            detail=f"output_dir={self.output_dir}",
        )

    # ------------------------------------------------------------------
    def print_ticket(self, rendered: RenderedTicket) -> PrintResult:
        started = time.perf_counter()
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        nro = rendered.metadata.get("numero", str(rendered.payload.comprobante.numero))
        safe_nro = nro.replace("/", "-").replace(" ", "")
        preview_id = f"{ts}-{safe_nro}"

        pdf_path = self.output_dir / f"{preview_id}.pdf"
        txt_path = self.output_dir / f"{preview_id}.txt"

        # Plain text dump (good for diffs and console preview)
        txt_content = "\n".join(rendered.lines)
        txt_path.write_text(txt_content, encoding="utf-8")

        # PDF — render with reportlab
        self._render_pdf(rendered, pdf_path)

        log.info(
            "mock printer wrote ticket %s (%d bytes ESC/POS, %d lines)",
            preview_id,
            len(rendered.escpos_bytes),
            len(rendered.lines),
        )
        # Console preview — lets devs see the ticket without opening the PDF
        log.info("\n----- TICKET %s -----\n%s\n----- END -----", preview_id, txt_content)

        self._last_id = preview_id
        duration_ms = int((time.perf_counter() - started) * 1000)
        return PrintResult(
            printed=True,
            preview_id=preview_id,
            duration_ms=duration_ms,
            detail=f"pdf={pdf_path.name}",
        )

    # ------------------------------------------------------------------
    def get_preview_path(self, preview_id: str) -> Path | None:
        """Return the PDF path for a given preview id, or None if not found."""
        # Disallow path traversal.
        safe = Path(preview_id).name
        candidate = self.output_dir / f"{safe}.pdf"
        return candidate if candidate.exists() else None

    @property
    def last_preview_id(self) -> str | None:
        return self._last_id

    # ------------------------------------------------------------------
    def _render_pdf(self, rendered: RenderedTicket, path: Path) -> None:
        """Render the ticket lines as a thermal-receipt-style PDF.

        The page width matches the configured paper width (default 80mm).
        The height is computed from the number of lines + QR.
        """
        ancho_mm = rendered.payload.ancho_papel_mm
        page_w = ancho_mm * mm
        # Mono font Courier @ 9pt → roughly 5.4pt per char on 80mm = 48 chars
        font_size = 9 if ancho_mm >= 80 else 8
        line_h = font_size + 2  # pt

        # Estimate height
        n_lines = len(rendered.lines)
        qr_h = 60 * mm if rendered.qr_png else 0
        margin_v = 6 * mm
        page_h = (n_lines * line_h) + qr_h + (margin_v * 2) + 30 * mm

        c = canvas.Canvas(str(path), pagesize=(page_w, page_h))
        c.setFont("Courier", font_size)

        margin_h = 3 * mm
        cursor_y = page_h - margin_v

        for raw_line in rendered.lines:
            stripped = raw_line.strip()

            # QR placeholder
            if stripped == "[QR AFIP]" and rendered.qr_png:
                from reportlab.lib.utils import ImageReader

                qr_size = 35 * mm
                qr_x = (page_w - qr_size) / 2
                cursor_y -= qr_size + 2 * mm
                c.drawImage(
                    ImageReader(io.BytesIO(rendered.qr_png)),
                    qr_x,
                    cursor_y,
                    width=qr_size,
                    height=qr_size,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                cursor_y -= 2 * mm
                continue

            # Big TOTAL line
            if stripped.startswith("TOTAL") and "$" in stripped:
                c.setFont("Courier-Bold", font_size + 3)
                c.drawString(margin_h, cursor_y, raw_line.rstrip())
                c.setFont("Courier", font_size)
                cursor_y -= line_h + 4
                continue

            # Big banners (razon social + comprobante header)
            razon_social = rendered.payload.comercio.razon_social.upper()
            if razon_social and razon_social in raw_line.upper():
                c.setFont("Courier-Bold", font_size + 2)
                c.drawString(margin_h, cursor_y, raw_line.rstrip())
                c.setFont("Courier", font_size)
                cursor_y -= line_h + 2
                continue

            from ..ticket.templates import header_label

            banner = header_label(
                rendered.payload.tipo, rendered.payload.comprobante.tipo_letra
            )
            if banner and banner in raw_line:
                c.setFont("Courier-Bold", font_size + 2)
                c.drawString(margin_h, cursor_y, raw_line.rstrip())
                c.setFont("Courier", font_size)
                cursor_y -= line_h + 2
                continue

            c.drawString(margin_h, cursor_y, raw_line.rstrip())
            cursor_y -= line_h

        c.showPage()
        c.save()
