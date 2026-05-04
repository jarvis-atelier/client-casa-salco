"""Factory para elegir el OCR provider segun config."""
from __future__ import annotations

import logging

from app.config import get_settings

from . import OcrProvider
from .mock_provider import MockProvider

logger = logging.getLogger(__name__)


def get_ocr_provider() -> OcrProvider:
    """Devuelve el provider OCR segun `OCR_MODE`.

    Si el mode pide un provider real pero falta la API key, hace fallback a mock con warning.
    """
    settings = get_settings()
    mode = settings.OCR_MODE

    if mode == "mock":
        return MockProvider()

    if mode == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            logger.warning(
                "OCR_MODE=anthropic pero ANTHROPIC_API_KEY no seteada — fallback a mock"
            )
            return MockProvider()
        from .anthropic_provider import AnthropicVisionProvider

        return AnthropicVisionProvider(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.ANTHROPIC_MODEL,
        )

    if mode == "gemini":
        if not settings.GEMINI_API_KEY:
            logger.warning(
                "OCR_MODE=gemini pero GEMINI_API_KEY no seteada — fallback a mock"
            )
            return MockProvider()
        from .gemini_provider import GeminiVisionProvider

        return GeminiVisionProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )

    raise ValueError(f"OCR_MODE desconocido: {mode}")
