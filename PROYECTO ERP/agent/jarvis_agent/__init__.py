"""Jarvis POS Agent — local printing bridge for 3NSTAR ESC/POS thermal printers.

This package runs on each POS terminal as an HTTP service on port 9123. The
web POS sends ticket payloads to it; the agent renders ESC/POS bytes and
sends them to the configured printer (USB / network) — or, in mock mode,
writes a PDF preview to disk for development without hardware.
"""
__version__ = "0.1.0"
