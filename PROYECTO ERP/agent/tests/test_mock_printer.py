"""Tests for the mock PDF printer."""
from __future__ import annotations

from pathlib import Path

from jarvis_agent.ticket.renderer import render_ticket


def test_mock_writes_pdf_to_disk(mock_printer, factura_a_payload):
    rendered = render_ticket(factura_a_payload)
    result = mock_printer.print_ticket(rendered)

    assert result.printed is True
    assert result.preview_id is not None

    pdf_path = Path(mock_printer.output_dir) / f"{result.preview_id}.pdf"
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 500  # at least a few hundred bytes
    # PDF magic
    with pdf_path.open("rb") as f:
        assert f.read(4) == b"%PDF"


def test_mock_writes_txt_dump(mock_printer, factura_a_payload):
    rendered = render_ticket(factura_a_payload)
    result = mock_printer.print_ticket(rendered)

    txt_path = Path(mock_printer.output_dir) / f"{result.preview_id}.txt"
    assert txt_path.exists()
    content = txt_path.read_text(encoding="utf-8")
    assert "FACTURA A" in content
    assert "CAE: 30686532297689" in content


def test_mock_status_always_ready(mock_printer):
    s = mock_printer.status()
    assert s.status == "ready"
    assert s.driver == "mock"
    assert s.online is True


def test_get_preview_path_returns_existing_pdf(mock_printer, factura_a_payload):
    rendered = render_ticket(factura_a_payload)
    result = mock_printer.print_ticket(rendered)
    pdf = mock_printer.get_preview_path(result.preview_id)
    assert pdf is not None
    assert pdf.exists()


def test_get_preview_path_returns_none_for_unknown(mock_printer):
    assert mock_printer.get_preview_path("nope") is None


def test_get_preview_path_blocks_path_traversal(mock_printer, factura_a_payload):
    """Trying ../etc/passwd should not escape the output dir."""
    assert mock_printer.get_preview_path("../etc/passwd") is None
    assert mock_printer.get_preview_path("..\\..\\windows\\config") is None
