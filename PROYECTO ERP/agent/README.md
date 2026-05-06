# Jarvis POS Agent

Local sidecar HTTP service that bridges the Jarvis Core web POS to physical
**3NSTAR ESC/POS thermal printers** (PRP-080 USB and PRP-080N Ethernet are the
typical models). Each POS terminal runs its own instance on `127.0.0.1:9123`.

The web app does **not** talk directly to the printer. Instead, after emitting
a sale, the frontend POSTs the ticket payload to the agent and the agent:

1. Validates and renders the payload (Pydantic).
2. Generates ESC/POS bytes (text + AFIP QR raster image).
3. Sends them to the configured driver (`mock`, `usb`, `network`).

In **mock mode** (the default), the agent writes a PDF preview to disk and
exposes it at `/preview/<id>` — perfect for development without hardware.

## Quick start (development, mock mode)

```bash
cd D:\repo\00-omar\CASA SALCO\PROYECTO ERP\agent
"C:\Users\Administrador\AppData\Local\Programs\Python\Python311\python.exe" -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env
.venv\Scripts\python -m jarvis_agent
```

You should see `Jarvis POS Agent listo en http://127.0.0.1:9123 (driver=mock)`.

Sanity-check:

```bash
curl http://localhost:9123/status
# {"driver":"mock","status":"ready","online":true,...}
```

## Endpoints

| Method | Path                | Description                                     |
|--------|---------------------|-------------------------------------------------|
| GET    | `/health`           | Liveness probe                                  |
| GET    | `/status`           | Printer status (driver, papel, online)          |
| POST   | `/print/ticket`     | Render + print a ticket (returns preview URL)   |
| GET    | `/preview/<id>`     | Serves the mock-printer PDF                     |

### `POST /print/ticket` payload

See [`jarvis_agent/ticket/renderer.py`](jarvis_agent/ticket/renderer.py) for
the authoritative Pydantic schemas. Minimal body:

```json
{
  "tipo": "ticket",
  "comercio": {"razon_social":"CASA SALCO SA","cuit":"30-12345678-9"},
  "sucursal": {"codigo":"SUC01","nombre":"CASA SALCO Centro","punto_venta":1},
  "comprobante": {"tipo_letra":"X","numero":12,"fecha":"2026-04-24T18:30:00"},
  "items": [{
    "codigo":"ARRZ-001","descripcion":"Arroz 1kg",
    "cantidad":2,"precio_unitario":"1100.00","subtotal":"2200.00"
  }],
  "totales": {"subtotal":"2200.00","total":"2662.00"},
  "pagos": [{"medio":"efectivo","monto":"2700.00"}]
}
```

For an A/B/C invoice add the `afip` field (`cae`, `vencimiento`, `qr_url`) so
the agent can render the regulatory QR.

## Configuration (`.env`)

| Variable                    | Default                | Notes                                     |
|-----------------------------|------------------------|-------------------------------------------|
| `JARVIS_AGENT_HOST`         | `127.0.0.1`            |                                           |
| `JARVIS_AGENT_PORT`         | `9123`                 |                                           |
| `PRINTER_MODE`              | `mock`                 | `mock` \| `usb` \| `network`              |
| `PRINTER_USB_VENDOR`        | `0x0fe6`               | 3NSTAR PRP-080 default                    |
| `PRINTER_USB_PRODUCT`       | `0x811e`               | varies per model                          |
| `PRINTER_NETWORK_HOST`      | `192.168.1.50`         | for Ethernet model                        |
| `PRINTER_NETWORK_PORT`      | `9100`                 | RAW socket protocol                       |
| `PRINTER_PAPER_WIDTH_MM`    | `80`                   | `58` or `80`                              |
| `OUTPUT_DIR`                | `output`               | mock printer drops PDFs here              |
| `CORS_ORIGINS`              | `http://localhost:5173,http://localhost:1420` | comma-separated allow list |

## Configuring a 3NSTAR PRP-080 over USB (Windows)

The PRP-080 ships with an OEM print-driver that grabs the USB device — pyusb
can't open it. To use raw USB you must:

1. Download [Zadig](https://zadig.akeo.ie/).
2. Plug the printer in, run Zadig as admin.
3. Pick the printer device (USB Printing Support / 3NSTAR / PRP-080).
4. Replace the driver with `libusb-win32` or `WinUSB`.
5. Find the vendor + product IDs (Zadig shows them, e.g. `0fe6` / `811e`).
6. Set `PRINTER_MODE=usb`, `PRINTER_USB_VENDOR=0x0fe6`, etc. in `.env`.

> **Strongly recommended:** for stable production use, prefer the Ethernet
> model (PRP-080N) with `PRINTER_MODE=network`. It avoids Windows USB driver
> issues entirely.

## Configuring a 3NSTAR Ethernet printer

1. Connect the printer to the LAN, configure a static IP via the manufacturer
   manual (most ship at `192.168.1.50`).
2. From the agent host, `ping <ip>` and `telnet <ip> 9100` to confirm reach.
3. Set `PRINTER_MODE=network`, `PRINTER_NETWORK_HOST=<ip>`,
   `PRINTER_NETWORK_PORT=9100`.

## Running tests

```bash
.venv\Scripts\pytest tests/
```

## Packaging as a Windows Service (TODO)

For unattended installations the agent should run as a Windows service so
operators don't see a console window. Sketch (not implemented yet):

```python
# scripts/install_service.py
import win32service, win32serviceutil
from jarvis_agent.app import create_app
# ... wrap with pywin32 ServiceFramework
```

We'll deliver this in a later phase; today the agent is launched manually
(`python -m jarvis_agent`) or via a Task Scheduler entry.

## Troubleshooting

| Symptom                                | Likely cause / fix                                       |
|----------------------------------------|----------------------------------------------------------|
| `usb_open_failed: [Errno 13] Access denied` | Printer is bound to OEM driver — use Zadig to switch to libusb |
| `network_connect_failed: timed out`    | Wrong IP, firewall, or printer offline                   |
| Receipt prints garbled accents         | Make sure the printer is on CP437/CP858 (default works)  |
| QR prints as black square              | Image too wide for paper — reduce `size_px` in renderer  |
| `pyusb DLL not found`                  | Install libusb-1.0 (Windows: `pacman -S mingw64/libusb`) |

## Architecture

```
+----------------+        HTTP POST /print/ticket         +----------------+
| Browser POS    |  -------------------------------->     | jarvis-agent   |
| (Vite :5173)   |  <-------------------------------      | (Flask :9123)  |
+----------------+        {printed, preview_url}          +-------+--------+
                                                                  |
                                                                  v
                                                +-----------------+----------------+
                                                | mock | USB driver | Network drv |
                                                +-----------------+----------------+
                                                          |
                                                          v
                                              +---------------------------+
                                              | PDF (output/) | 3NSTAR    |
                                              +---------------------------+
```

The agent is **completely independent** from the Flask backend at port 5000.
It does not access the database. The frontend is responsible for assembling
the payload from the `Factura` response + commerce/sucursal data.
