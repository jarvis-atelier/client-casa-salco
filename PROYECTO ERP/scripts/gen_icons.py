"""Genera iconos PWA para Jarvis Core.

Apple aesthetic: cuadrado Apple Blue (#007AFF) con texto "JC" en blanco.
Genera 4 archivos en frontend/public/icons:
- icon-192.png      (rounded square, no margins extra)
- icon-512.png
- icon-192-maskable.png  (con padding del 12% para safe area)
- icon-512-maskable.png

También crea apple-touch-icon.png (180×180) y favicon.svg.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Ruta absoluta a public/icons (corre desde cualquier cwd)
HERE = Path(__file__).resolve().parent
FRONTEND_PUBLIC = HERE.parent / "frontend" / "public"
ICONS_DIR = FRONTEND_PUBLIC / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

APPLE_BLUE = (0, 122, 255, 255)
WHITE = (255, 255, 255, 255)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Intenta cargar una fuente bold del sistema; cae a default si no hay."""
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",  # Segoe UI Bold
        "C:/Windows/Fonts/arialbd.ttf",  # Arial Bold
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _make_icon(size: int, padding_ratio: float = 0.0) -> Image.Image:
    """Genera un icono cuadrado Apple Blue con texto JC centrado.

    `padding_ratio`: fracción de espacio entre el borde y el "contenido visible"
    para iconos maskable (Android safe zone ≈ 10–12%).
    """
    img = Image.new("RGBA", (size, size), APPLE_BLUE)
    draw = ImageDraw.Draw(img)

    # Texto "JC" centrado (proporcional al área "segura")
    inner = size * (1 - 2 * padding_ratio)
    font_size = int(inner * 0.55)
    font = _load_font(font_size)

    text = "JC"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), text, fill=WHITE, font=font)

    return img


def main() -> None:
    print(f"Generando iconos en {ICONS_DIR}...")

    for size in (192, 512):
        path = ICONS_DIR / f"icon-{size}.png"
        _make_icon(size, padding_ratio=0.0).save(path, format="PNG")
        print(f"  - {path.name} ({size}x{size})")

    for size in (192, 512):
        path = ICONS_DIR / f"icon-{size}-maskable.png"
        # Padding 12% para que el "contenido visible" caiga en safe zone Android
        _make_icon(size, padding_ratio=0.12).save(path, format="PNG")
        print(f"  - {path.name} ({size}x{size}) maskable")

    # apple-touch-icon (iOS)
    apple = _make_icon(180, padding_ratio=0.0)
    apple_path = FRONTEND_PUBLIC / "apple-touch-icon.png"
    apple.save(apple_path, format="PNG")
    print(f"  - {apple_path.name} (180x180)")

    # favicon.svg simple (cuadrado azul con texto)
    favicon_svg = FRONTEND_PUBLIC / "favicon.svg"
    favicon_svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#007AFF"/>
  <text x="32" y="42" font-family="Helvetica, Arial, sans-serif" font-size="32" font-weight="700" fill="#fff" text-anchor="middle">JC</text>
</svg>
""",
        encoding="utf-8",
    )
    print(f"  - {favicon_svg.name}")

    print("OK")


if __name__ == "__main__":
    main()
