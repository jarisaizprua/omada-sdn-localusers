"""Diagnóstico de la conexión con el Omada Open API.

Ejecuta cada paso del flujo Authorization Code por separado y explica, en
español, qué revisar según en qué paso falle. Útil para aislar problemas de
configuración sin tener que leer logs de Streamlit.

Uso:
    python scripts/test_omada_connection.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
import urllib3  # noqa: E402

from config import get_settings  # noqa: E402


def mask(value: str, visible: int = 4) -> str:
    if not value:
        return "(vacío)"
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


def main() -> None:
    settings = get_settings()
    if not settings.omada_verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("== Diagnóstico de conexión Omada Open API ==\n")
    print(f"OMADA_BASE_URL           : {settings.omada_base_url}")
    print(f"OMADA_OMADAC_ID           : {settings.omada_omadac_id}")
    print(f"OMADA_CLIENT_ID           : {mask(settings.omada_client_id)}")
    print(f"OMADA_CLIENT_SECRET       : {mask(settings.omada_client_secret)}")
    print(f"OMADA_CONTROLLER_USERNAME : {settings.omada_controller_username}")
    print(f"OMADA_CONTROLLER_PASSWORD : {mask(settings.omada_controller_password, visible=0)} "
          f"({len(settings.omada_controller_password)} caracteres)")
    print(f"OMADA_VERIFY_SSL          : {settings.omada_verify_ssl}\n")

    base_url = settings.omada_base_url.rstrip("/")
    session = requests.Session()

    # --- Paso 0: ¿el controlador responde en absoluto? -------------------
    print("[0] Probando que el controlador responde...")
    try:
        resp = session.get(base_url, timeout=10, verify=settings.omada_verify_ssl)
        print(f"    OK - el host respondió con HTTP {resp.status_code} (esto es normal aunque no sea 200).\n")
    except requests.exceptions.SSLError as exc:
        print(f"    ERROR de certificado SSL: {exc}")
        print("    -> Si usas un certificado autofirmado, pon OMADA_VERIFY_SSL=false en tu .env.\n")
        return
    except requests.exceptions.RequestException as exc:
        print(f"    ERROR de red: {exc}")
        print(
            "    -> Revisa que OMADA_BASE_URL sea accesible desde esta máquina "
            "(incluye el puerto, ej. :8043) y que no haya firewall bloqueando.\n"
        )
        return

    # --- Paso 1: login (usuario/contraseña del controlador) --------------
    print("[1] POST /openapi/authorize/login (usuario/contraseña del controlador)...")
    try:
        resp = session.post(
            f"{base_url}/openapi/authorize/login",
            params={"client_id": settings.omada_client_id, "omadac_id": settings.omada_omadac_id},
            json={
                "username": settings.omada_controller_username,
                "password": settings.omada_controller_password,
            },
            headers={"Content-Type": "application/json"},
            timeout=15,
            verify=settings.omada_verify_ssl,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        print(f"    ERROR de red/HTTP: {exc}\n")
        return

    if data.get("errorCode") != 0:
        print(f"    ERROR -> errorCode={data.get('errorCode')} msg={data.get('msg')}\n")
        _print_login_hints(data.get("errorCode"))
        return

    csrf_token = data["result"]["csrfToken"]
    session_id = data["result"]["sessionId"]
    print("    OK - login correcto, csrfToken y sessionId obtenidos.\n")

    # --- Paso 2: authorization code --------------------------------------
    print("[2] POST /openapi/authorize/code (obtener authorization code)...")
    resp = session.post(
        f"{base_url}/openapi/authorize/code",
        params={
            "client_id": settings.omada_client_id,
            "omadac_id": settings.omada_omadac_id,
            "response_type": "code",
        },
        headers={
            "Content-Type": "application/json",
            "Csrf-Token": csrf_token,
            "Cookie": f"TPOMADA_SESSIONID={session_id}",
        },
        timeout=15,
        verify=settings.omada_verify_ssl,
    )
    data = resp.json()
    if data.get("errorCode") != 0:
        print(f"    ERROR -> errorCode={data.get('errorCode')} msg={data.get('msg')}\n")
        print(
            "    -> Revisa que la app en el controlador esté creada en modo "
            "'Authorization Code' (no 'Client Credentials') y que OMADA_CLIENT_ID "
            "corresponda a esa app.\n"
        )
        return

    auth_code = data["result"]
    print("    OK - authorization code obtenido.\n")

    # --- Paso 3: intercambio por access token -----------------------------
    print("[3] POST /openapi/authorize/token (intercambiar code por access token)...")
    resp = session.post(
        f"{base_url}/openapi/authorize/token",
        params={"grant_type": "authorization_code", "code": auth_code},
        json={"client_id": settings.omada_client_id, "client_secret": settings.omada_client_secret},
        headers={"Content-Type": "application/json"},
        timeout=15,
        verify=settings.omada_verify_ssl,
    )
    data = resp.json()
    if data.get("errorCode") != 0:
        print(f"    ERROR -> errorCode={data.get('errorCode')} msg={data.get('msg')}\n")
        print(
            "    -> Revisa OMADA_CLIENT_SECRET: es el único dato que no se ha usado "
            "todavía en los pasos anteriores, así que un fallo aquí casi siempre "
            "significa que el Client Secret no corresponde al Client ID, o que se "
            "regeneró en el controlador después de copiarlo.\n"
        )
        return

    result = data["result"]
    print("    OK - access token obtenido correctamente.")
    print(f"    accessToken : {mask(result['accessToken'])}")
    print(f"    expiresIn   : {result['expiresIn']} segundos")
    print(f"    refreshToken: {mask(result['refreshToken'])}\n")

    # --- Paso 4: primera llamada real a la API ----------------------------
    print("[4] GET /openapi/v1/{omadacId}/sites (primera llamada real)...")
    resp = session.get(
        f"{base_url}/openapi/v1/{settings.omada_omadac_id}/sites",
        params={"page": 1, "pageSize": 10},
        headers={"Authorization": f"AccessToken={result['accessToken']}"},
        timeout=15,
        verify=settings.omada_verify_ssl,
    )
    data = resp.json()
    if data.get("errorCode") != 0:
        print(f"    ERROR -> errorCode={data.get('errorCode')} msg={data.get('msg')}\n")
        return

    sites = data["result"].get("data", [])
    print(f"    OK - {len(sites)} sitio(s) encontrado(s):")
    for s in sites:
        print(f"        - {s.get('name')} (siteId={s.get('siteId')})")

    print("\n✅ Todo el flujo funcionó correctamente. El portal debería conectar sin problemas.")


def _print_login_hints(error_code) -> None:
    print("    Posibles causas de 'Invalid username or password' (errorCode=-30109):")
    print("      1. La contraseña tiene un '#' o espacios y el .env la cortó como comentario:")
    print('         envuélvela en comillas, ej: OMADA_CONTROLLER_PASSWORD="mi#pass 123"')
    print("      2. Hay un espacio o salto de línea invisible al pegarla en el .env (típico en Windows).")
    print("      3. Estás usando el TP-Link ID (cuenta cloud) en vez de un usuario LOCAL del")
    print("         controlador. Si tu controlador es Cloud-Based, crea/usa un operador local.")
    print("      4. Usuario o contraseña con un simple typo, o cuenta bloqueada temporalmente")
    print("         por varios intentos fallidos (espera unos minutos y reintenta).")
    print("      5. Prueba a iniciar sesión con ESTAS MISMAS credenciales directamente en la")
    print(f"         interfaz web del controlador ({get_settings().omada_base_url}) para confirmar")
    print("         que son válidas fuera de este script.")


if __name__ == "__main__":
    main()
