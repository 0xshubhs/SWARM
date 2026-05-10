"""TurboQuant worker entry point — imports server app."""
from __future__ import annotations

from worker.server.main import app

__all__ = ["app"]