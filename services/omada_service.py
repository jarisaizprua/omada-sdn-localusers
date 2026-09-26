from __future__ import annotations

import streamlit as st

from config import get_settings
from omada_client.auth import OmadaAuthenticator, OmadaCredentials
from omada_client.client import OmadaClient
from omada_client.token_store import TokenStore


@st.cache_resource(show_spinner=False)
def get_omada_client() -> OmadaClient:
    """Cliente Omada compartido por toda la app (una sola instancia por
    proceso gracias a st.cache_resource)."""
    settings = get_settings()
    credentials = OmadaCredentials(
        base_url=settings.omada_base_url,
        client_id=settings.omada_client_id,
        client_secret=settings.omada_client_secret,
        omadac_id=settings.omada_omadac_id,
        controller_username=settings.omada_controller_username,
        controller_password=settings.omada_controller_password,
        verify_ssl=settings.omada_verify_ssl,
    )
    token_store = TokenStore(settings.omada_token_cache_path)
    authenticator = OmadaAuthenticator(credentials, token_store)
    return OmadaClient(
        authenticator,
        base_url=settings.omada_base_url,
        omadac_id=settings.omada_omadac_id,
        verify_ssl=settings.omada_verify_ssl,
        min_request_interval=settings.omada_min_request_interval,
        timeout=settings.omada_request_timeout,
    )


@st.cache_data(ttl=120, show_spinner="Consultando sitios en Omada...")
def get_sites_cached() -> list[dict]:
    client = get_omada_client()
    return client.get_all_sites()


def clear_sites_cache() -> None:
    get_sites_cached.clear()


@st.cache_data(ttl=30, show_spinner="Consultando usuarios locales...")
def get_local_users_cached(site_id: str) -> list[dict]:
    """Lista de usuarios locales de un site, cacheada 30s para que cambiar de
    pestaña o repetir una consulta no dispare otra llamada de red a Omada.
    Cualquier operación de crear/editar/eliminar debe invalidar este caché
    para ese site_id llamando a clear_local_users_cache(site_id)."""
    from omada_client.users import list_all_local_users

    client = get_omada_client()
    return list_all_local_users(client, site_id)


def clear_local_users_cache(site_id: str | None = None) -> None:
    """Invalida el caché de usuarios locales. Sin argumentos, limpia todos
    los sites cacheados (Streamlit no permite invalidar una sola clave de
    st.cache_data directamente, así que se limpia toda la función)."""
    get_local_users_cached.clear()
