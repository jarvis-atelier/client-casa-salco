"""Captura screenshots de cada pantalla por rol para los manuales de usuario.

Uso:
    cd backend
    .venv/Scripts/python ../../scripts/capture_screenshots.py

Genera PNGs en `manuals/screenshots/<rol>/<pantalla>.png`.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://127.0.0.1:5005/casasalco"
ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = ROOT / "manuals" / "screenshots"

# (path, slug-del-archivo, label-humano, [acciones extra: clicks/waits])
ALL_SCREENS: list[tuple[str, str, str]] = [
    ("/", "01-dashboard", "Dashboard"),
    ("/pos", "02-pos", "Punto de venta"),
    ("/facturas", "03-facturas", "Facturas"),
    ("/movimientos", "04-movimientos", "Movimientos"),
    ("/pagos", "05-pagos", "Calendario de pagos"),
    ("/articulos", "06-articulos", "Artículos"),
    ("/clientes", "07-clientes", "Clientes"),
    ("/proveedores", "08-proveedores", "Proveedores"),
    ("/compras/ocr", "09-compras", "Compras (OCR)"),
    ("/stock", "10-stock", "Stock"),
    ("/stock/reposicion", "11-reposicion", "Reposición"),
    ("/sucursales", "12-sucursales", "Sucursales"),
    ("/consultas", "13-consultas", "Consultas"),
    ("/exports", "14-exports", "Exportar"),
    ("/mantenimiento", "15-mantenimiento", "Mantenimiento"),
]

# Pantallas que cada rol puede ver (alineado con `lib/permissions.ts`).
ROLE_SCREENS: dict[str, set[str]] = {
    "admin": {p for p, _, _ in ALL_SCREENS},
    "supervisor": {p for p, _, _ in ALL_SCREENS}
    - {"/sucursales", "/mantenimiento"},
    "cajero": {"/", "/pos", "/facturas", "/movimientos", "/articulos", "/clientes", "/stock"},
    "contador": {
        "/",
        "/facturas",
        "/movimientos",
        "/pagos",
        "/articulos",
        "/clientes",
        "/proveedores",
        "/compras/ocr",
        "/consultas",
        "/exports",
    },
}

ROLE_CREDS: dict[str, tuple[str, str]] = {
    "admin": ("admin@casasalco.app", "admin123"),
    "supervisor": ("supervisor1@casasalco.app", "super123"),
    "cajero": ("cajero1@casasalco.app", "cajero123"),
    "contador": ("contador@casasalco.app", "contador123"),
}


def login(page: Page, email: str, password: str) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill('input[id="email"]', email)
    page.fill('input[id="password"]', password)
    # Botón submit del form
    page.click('button[type="submit"]')
    # Espera a salir de /login
    page.wait_for_url(lambda url: "/login" not in url, timeout=15_000)
    # Pequeño respiro para que termine el primer fetch del dashboard
    page.wait_for_load_state("networkidle", timeout=10_000)


def capture_role(role: str, page: Page) -> int:
    out_dir = SCREENSHOTS_DIR / role
    out_dir.mkdir(parents=True, exist_ok=True)
    email, pwd = ROLE_CREDS[role]
    print(f"\n[{role}] login {email}")
    login(page, email, pwd)

    allowed = ROLE_SCREENS[role]
    captured = 0
    for path, slug, label in ALL_SCREENS:
        if path not in allowed:
            continue
        url = f"{BASE}{path}"
        print(f"  ->{slug} {label}  ({url})")
        try:
            page.goto(url, wait_until="networkidle", timeout=20_000)
            time.sleep(1.0)
            try:
                page.screenshot(
                    path=str(out_dir / f"{slug}.png"),
                    full_page=True,
                )
            except Exception:
                # Algunas pantallas tienen tablas largas que generan
                # screenshots > 32k px de alto. Fallback al viewport.
                print(f"    [INFO] full_page falló, usando viewport para {slug}")
                page.screenshot(
                    path=str(out_dir / f"{slug}.png"),
                    full_page=False,
                )
            captured += 1
        except Exception as e:
            print(f"    [WARN] fallo capturando {slug}: {e}")
    return captured


def main() -> int:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    roles = sys.argv[1:] or list(ROLE_CREDS.keys())
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for role in roles:
                if role not in ROLE_CREDS:
                    print(f"[{role}] desconocido — skip")
                    continue
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                page = ctx.new_page()
                try:
                    n = capture_role(role, page)
                    print(f"[{role}] {n} pantallas capturadas")
                finally:
                    ctx.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
