from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests
import urllib3

from .exceptions import OmadaAuthError
from .token_store import TokenData, TokenStore

logger = logging.getLogger(__name__)

# Márgenes de seguridad documentados por TP-Link para el Omada Open API:
# el access_token dura ~2 horas y el refresh_token ~14 días. Se refrescan
# ANTES de expirar para no dejar caer ninguna petición.
REFRESH_MARGIN_SECONDS = 120
ACCESS_TOKEN_DEFAULT_LIFETIME = 2 * 3600
REFRESH_TOKEN_LIFETIME_SECONDS = 14 * 24 * 3600


@dataclass
class OmadaCredentials:
    base_url: str
    client_id: str
    client_secret: str
    omadac_id: str
    controller_username: str
    controller_password: str
    verify_ssl: bool = True


class OmadaAuthenticator:
    """
    Implementa el flujo OAuth2 **Authorization Code** del Omada Open API:

        1. POST /openapi/authorize/login   -> csrfToken + sessionId
        2. POST /openapi/authorize/code    -> authorization code
        3. POST /openapi/authorize/token   -> access_token + refresh_token
        4. POST /openapi/authorize/token   -> (grant_type=refresh_token) nuevo access_token

    Referencia: Omada Open API Guide, sección "Organization Level Open API
    Access Process > Authorization Code Mode"
    (https://omada-northbound-docs.tplinkcloud.com/).

    Nota: a diferencia de un OAuth "Authorization Code" web clásico con
    redirect interactivo, el Omada Open API resuelve el login con las
    credenciales de un usuario del controlador (paso 1) y a partir de ahí
    obtiene el código de forma programática (paso 2). Por eso esta clase
    necesita, además de client_id/client_secret, un usuario y contraseña
    de una cuenta de servicio del controlador.
    """

    def __init__(self, credentials: OmadaCredentials, token_store: TokenStore):
        self.creds = credentials
        self.token_store = token_store
        self._session = requests.Session()
        if not credentials.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ---------------------------------------------------------- internals --
    def _url(self, path: str) -> str:
        return f"{self.creds.base_url.rstrip('/')}{path}"

    def _post(self, path: str, *, params=None, json_body=None, headers=None) -> dict:
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        resp = self._session.post(
            self._url(path),
            params=params,
            json=json_body,
            headers=request_headers,
            timeout=15,
            verify=self.creds.verify_ssl,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errorCode") != 0:
            raise OmadaAuthError(f"{path} -> errorCode={data.get('errorCode')} msg={data.get('msg')}")
        return data["result"]

    def _login(self) -> tuple[str, str]:
        result = self._post(
            "/openapi/authorize/login",
            params={"client_id": self.creds.client_id, "omadac_id": self.creds.omadac_id},
            json_body={
                "username": self.creds.controller_username,
                "password": self.creds.controller_password,
            },
        )
        return result["csrfToken"], result["sessionId"]

    def _authorization_code(self, csrf_token: str, session_id: str) -> str:
        result = self._post(
            "/openapi/authorize/code",
            params={
                "client_id": self.creds.client_id,
                "omadac_id": self.creds.omadac_id,
                "response_type": "code",
            },
            headers={
                "Csrf-Token": csrf_token,
                "Cookie": f"TPOMADA_SESSIONID={session_id}",
            },
        )
        return result  # el código de autorización viene directamente en "result"

    def _exchange_code(self, code: str) -> dict:
        return self._post(
            "/openapi/authorize/token",
            params={"grant_type": "authorization_code", "code": code},
            json_body={"client_id": self.creds.client_id, "client_secret": self.creds.client_secret},
        )

    def _refresh(self, refresh_token: str) -> dict:
        return self._post(
            "/openapi/authorize/token",
            params={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.creds.client_id,
                "client_secret": self.creds.client_secret,
            },
        )

    def _full_login_flow(self) -> TokenData:
        logger.info("Omada: iniciando flujo completo de autorización (login -> code -> token)")
        csrf_token, session_id = self._login()
        code = self._authorization_code(csrf_token, session_id)
        result = self._exchange_code(code)
        return self._store_tokens(result)

    def _store_tokens(self, result: dict) -> TokenData:
        now = time.time()
        expires_in = result.get("expiresIn", ACCESS_TOKEN_DEFAULT_LIFETIME)
        token_data: TokenData = {
            "access_token": result["accessToken"],
            "refresh_token": result["refreshToken"],
            "token_type": result.get("tokenType", "bearer"),
            "obtained_at": now,
            "expires_at": now + float(expires_in),
            "refresh_expires_at": now + REFRESH_TOKEN_LIFETIME_SECONDS,
        }
        self.token_store.save(token_data)
        return token_data

    # ------------------------------------------------------------ public --
    def get_valid_access_token(self, force_refresh: bool = False) -> str:
        """Devuelve un access_token utilizable, renovándolo o reautenticando
        automáticamente cuando hace falta."""
        cached = None if force_refresh else self.token_store.load()
        now = time.time()

        if cached and now < cached["expires_at"] - REFRESH_MARGIN_SECONDS:
            return cached["access_token"]

        if cached and now < cached.get("refresh_expires_at", 0):
            try:
                logger.info("Omada: renovando access_token con refresh_token")
                refreshed = self._refresh(cached["refresh_token"])
                token_data = self._store_tokens(refreshed)
                return token_data["access_token"]
            except OmadaAuthError:
                logger.warning("Omada: refresh_token inválido o expirado, se repite el login completo")

        token_data = self._full_login_flow()
        return token_data["access_token"]

    def invalidate(self) -> None:
        self.token_store.clear()
