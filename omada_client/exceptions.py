from __future__ import annotations

from typing import Any, Optional


class OmadaError(Exception):
    """Error base para cualquier fallo relacionado con la API de Omada."""


class OmadaAuthError(OmadaError):
    """Fallo durante el flujo OAuth2 (login, authorization code, token)."""


class OmadaAPIError(OmadaError):
    """La API respondió correctamente a nivel HTTP pero con errorCode != 0."""

    def __init__(self, error_code: Optional[int], message: str, payload: Optional[dict[str, Any]] = None):
        self.error_code = error_code
        self.message = message
        self.payload = payload
        super().__init__(f"[Omada errorCode={error_code}] {message}")
