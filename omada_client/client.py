from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

from .auth import OmadaAuthenticator
from .exceptions import OmadaAPIError

logger = logging.getLogger(__name__)

# Códigos de error que distintas versiones del controlador han devuelto para
# "token inválido/expirado" según reportes de la comunidad. Si tu controlador
# usa otro código, añádelo aquí: forzará una reautenticación automática en
# lugar de propagar el error al usuario.
TOKEN_ERROR_CODES = {-44112, -44113, -44114}


class OmadaClient:
    """Cliente HTTP genérico para el Omada Open API (Organization Level).

    Encapsula el prefijo ``/openapi/v1/{omadacId}/...``, la cabecera de
    autorización (``Authorization: AccessToken=...``) y el manejo de
    errores/``errorCode``, para que el resto de la aplicación trabaje con
    métodos Python normales en vez de construir URLs a mano.
    """

    def __init__(
        self,
        authenticator: OmadaAuthenticator,
        base_url: str,
        omadac_id: str,
        verify_ssl: bool = True,
        min_request_interval: float = 0.15,
        timeout: int = 15,
    ):
        self._auth = authenticator
        self._base_url = base_url.rstrip("/")
        self._omadac_id = omadac_id
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._min_interval = min_request_interval
        self._last_request_ts = 0.0
        self._session = requests.Session()

    # ------------------------------------------------------------ helpers --
    def _throttle(self) -> None:
        """Espaciado mínimo entre peticiones: el controlador limita la tasa
        de solicitudes por segundo (documentado ~10 req/s)."""
        elapsed = time.time() - self._last_request_ts
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def _full_url(self, path: str) -> str:
        return f"{self._base_url}/openapi/v1/{self._omadac_id}{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        retry_on_auth_error: bool = True,
    ) -> Any:
        self._throttle()
        token = self._auth.get_valid_access_token()
        headers = {"Authorization": f"AccessToken={token}"}

        resp = self._session.request(
            method,
            self._full_url(path),
            params=params,
            json=json_body,
            headers=headers,
            timeout=self._timeout,
            verify=self._verify_ssl,
        )
        self._last_request_ts = time.time()
        resp.raise_for_status()
        data = resp.json()
        error_code = data.get("errorCode")

        auth_looks_invalid = resp.status_code == 401 or error_code in TOKEN_ERROR_CODES
        if auth_looks_invalid and retry_on_auth_error:
            logger.warning("Omada: token rechazado (errorCode=%s), forzando reautenticación", error_code)
            self._auth.get_valid_access_token(force_refresh=True)
            return self.request(method, path, params=params, json_body=json_body, retry_on_auth_error=False)

        if error_code != 0:
            raise OmadaAPIError(error_code, data.get("msg", "Error desconocido"), payload=data)

        return data.get("result")

    # -------------------------------------------------------------- sites --
    def get_sites(self, page: int = 1, page_size: int = 100) -> dict:
        """GET /openapi/v1/{omadacId}/sites"""
        return self.request("GET", "/sites", params={"page": page, "pageSize": page_size})

    def get_all_sites(self) -> list[dict]:
        """Recorre todas las páginas y devuelve la lista completa de sites."""
        sites: list[dict] = []
        page = 1
        while True:
            result = self.get_sites(page=page, page_size=100)
            batch = result.get("data", [])
            sites.extend(batch)
            total = result.get("totalRows", len(sites))
            if not batch or page * 100 >= total:
                break
            page += 1
        return sites
