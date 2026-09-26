"""
omada_client
============

Cliente Python reutilizable para el Omada Open API (Organization Level),
usando el modo de autenticación **Authorization Code**.

Este paquete no depende de Streamlit ni de la base de datos del portal:
se puede copiar tal cual a cualquier otro proyecto (scripts de automatización,
otra app web, un bot, etc.) que necesite hablar con un controlador Omada.

Referencia oficial: https://omada-northbound-docs.tplinkcloud.com/
"""
from .auth import OmadaAuthenticator, OmadaCredentials
from .client import OmadaClient
from .exceptions import OmadaAPIError, OmadaAuthError, OmadaError
from .token_store import TokenStore

__all__ = [
    "OmadaAuthenticator",
    "OmadaCredentials",
    "OmadaClient",
    "OmadaError",
    "OmadaAuthError",
    "OmadaAPIError",
    "TokenStore",
]
