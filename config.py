"""
Configuración centralizada de la aplicación.

Todos los valores sensibles y específicos de la instalación (credenciales del
controlador Omada, rutas de base de datos, etc.) se leen desde variables de
entorno / archivo .env, para que este mismo código se pueda reutilizar en
cualquier despliegue de Omada sin tocar una sola línea.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Conexión al Omada Controller (Open API, modo Authorization Code) ---
    omada_base_url: str = Field(
        ..., description="URL base del controlador, ej: https://miomada.midominio.com:8043"
    )
    omada_client_id: str
    omada_client_secret: str
    omada_omadac_id: str = Field(..., description="omadacId del controlador/organización")
    omada_controller_username: str
    omada_controller_password: str
    omada_verify_ssl: bool = True
    omada_request_timeout: int = 15
    omada_min_request_interval: float = 0.15  # throttling para no superar el límite de la API

    # Solo informativo: la URL de login por navegador que muestra el controlador
    # para un flujo OAuth redirect clásico. Este portal no la usa (hace el login
    # directo por API), pero se conserva para mostrarla en el panel de Administración.
    omada_oauth_login_page_address: str = ""

    # --- Persistencia local ---
    app_db_path: Path = BASE_DIR / "data" / "portal.duckdb"
    omada_token_cache_path: Path = BASE_DIR / "data" / ".omada_token_cache.json"

    # --- Seguridad del portal ---
    app_secret_key: str = Field(..., description="Clave usada como sal/identificador de instalación")
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5

    # --- General ---
    app_name: str = "Omada WiFi User Portal"
    log_level: str = "INFO"

    # Limpia espacios/saltos de línea accidentales al copiar y pegar valores en
    # el .env (causa muy común de "Invalid username or password" en Windows).
    @field_validator(
        "omada_base_url",
        "omada_client_id",
        "omada_client_secret",
        "omada_omadac_id",
        "omada_controller_username",
        "omada_controller_password",
        mode="before",
    )
    @classmethod
    def _strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
