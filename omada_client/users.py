from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .client import OmadaClient

# Recurso "Hotspot Local Users" del Omada Open API: usuarios locales que se
# autentican contra el portal cautivo de WiFi (Settings > Authentication >
# Hotspot / Portal). Endpoints verificados contra un controlador real:
#   GET    /sites/{siteId}/hotspot/localusers
#   POST   /sites/{siteId}/hotspot/localusers
#   DELETE /sites/{siteId}/hotspot/localusers/{id}
# El endpoint de actualización (PATCH) sigue el patrón REST estándar usado
# por el resto de recursos del Omada Open API, pero no pudo confirmarse con
# una prueba en vivo: si tu controlador devuelve 404/405 al editar, revisa
# el Swagger embebido del propio controlador (Settings > Platform
# Integration > Open API > Documentación) y ajusta UPDATE_METHOD abajo.
LOCAL_USERS_PATH = "/sites/{site_id}/hotspot/localusers"
UPDATE_METHOD = "PATCH"


@dataclass
class LocalUserInput:
    """Datos que el operador del portal introduce para crear o editar un
    usuario local de WiFi. `to_payload()` genera el cuerpo JSON que espera
    la API (CreateLocalUserOpenApiVO)."""

    user_name: str
    password: str
    display_name: str = ""
    phone: str = ""
    enable: bool = True
    max_users: int = 1
    expiration_days: int = 0          # 0 = sin expiración
    binding_type: int = 0             # 0=sin vínculo, 1=estático, 2=dinámico
    mac_address: str = ""
    apply_to_all_portals: bool = True
    portals: list[str] = field(default_factory=list)
    down_limit_kbps: int = 0
    up_limit_kbps: int = 0
    traffic_limit_mb: int = 0

    def to_payload(self) -> dict:
        # NOTA: este controlador NO acepta expirationTime=0 como "sin
        # expiración" — la API exige que sea mayor al tiempo actual
        # (errorCode=-1001 "Parameter [expirationTime] must be greater than
        # the current time"). Cuando expiration_days es 0, usamos el mismo
        # valor por defecto que aplica la interfaz gráfica de Omada al crear
        # un usuario nuevo sin especificar fecha: el 31 de diciembre del año
        # en curso a las 23:59:59.
        if self.expiration_days and self.expiration_days > 0:
            expiration_dt = datetime.now() + timedelta(days=self.expiration_days)
        else:
            now = datetime.now()
            expiration_dt = datetime(now.year, 12, 31, 23, 59, 59)
            if expiration_dt <= now:  # ej. ejecutado el 31-dic después de las 23:59:59
                expiration_dt = datetime(now.year + 1, 12, 31, 23, 59, 59)
        expiration_time = int(expiration_dt.timestamp() * 1000)

        return {
            "userName": self.user_name,
            "password": self.password,
            "enable": self.enable,
            "expirationTime": expiration_time,
            "bindingType": self.binding_type,
            "macAddress": self.mac_address,
            "maxUsers": self.max_users,
            "name": self.display_name,
            "phone": self.phone,
            "rateLimit": {
                "mode": 2 if (self.down_limit_kbps or self.up_limit_kbps) else 0,
                "rateLimitProfileId": "",
                "customRateLimit": {
                    "downLimitEnable": bool(self.down_limit_kbps),
                    "downLimit": self.down_limit_kbps,
                    "upLimitEnable": bool(self.up_limit_kbps),
                    "upLimit": self.up_limit_kbps,
                },
            },
            "trafficLimitEnable": bool(self.traffic_limit_mb),
            "trafficLimit": self.traffic_limit_mb,
            "trafficLimitFrequency": 0,
            "portals": self.portals,
            "logout": True,
            "applyToAllPortals": self.apply_to_all_portals,
            "dailyLimitEnable": False,
            # NOTA: aunque dailyLimitEnable sea False, la API valida igual el
            # rango de estos campos (customTimeout debe estar entre 1 y 1440,
            # es decir minutos en un día -> errorCode=-1001 si se manda 0).
            "dailyLimit": {"authTimeout": 1, "customTimeout": 1440, "customTimeoutUnit": 1},
        }


def list_local_users(
    client: OmadaClient, site_id: str, page: int = 1, page_size: int = 1000
) -> tuple[list[dict], int]:
    """GET .../hotspot/localusers — una página de usuarios locales de un site."""
    result = client.request(
        "GET", LOCAL_USERS_PATH.format(site_id=site_id), params={"page": page, "pageSize": page_size}
    )
    return result.get("data", []), result.get("totalRows", 0)


def list_all_local_users(client: OmadaClient, site_id: str) -> list[dict]:
    """Recorre todas las páginas y devuelve la lista completa de usuarios locales."""
    users: list[dict] = []
    page = 1
    while True:
        batch, total = list_local_users(client, site_id, page=page, page_size=1000)
        users.extend(batch)
        if not batch or page * 1000 >= total:
            break
        page += 1
    return users


def find_user_by_username(client: OmadaClient, site_id: str, user_name: str) -> Optional[dict]:
    for user in list_all_local_users(client, site_id):
        if user.get("userName") == user_name:
            return user
    return None


def create_local_user(client: OmadaClient, site_id: str, data: LocalUserInput) -> dict:
    """POST .../hotspot/localusers"""
    return client.request("POST", LOCAL_USERS_PATH.format(site_id=site_id), json_body=data.to_payload())


def update_local_user(client: OmadaClient, site_id: str, user_id: str, data: LocalUserInput) -> dict:
    """PATCH .../hotspot/localusers/{id} — ver nota sobre UPDATE_METHOD arriba."""
    path = LOCAL_USERS_PATH.format(site_id=site_id) + f"/{user_id}"
    return client.request(UPDATE_METHOD, path, json_body=data.to_payload())


def delete_local_user(client: OmadaClient, site_id: str, user_id: str) -> dict:
    """DELETE .../hotspot/localusers/{id}"""
    path = LOCAL_USERS_PATH.format(site_id=site_id) + f"/{user_id}"
    return client.request("DELETE", path)
