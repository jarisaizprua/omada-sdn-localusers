from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from auth.session_guard import require_login
from config import get_settings
from omada_client.exceptions import OmadaError
from services.omada_service import clear_sites_cache, get_sites_cached
from utils.ui import apply_theme, page_header

st.set_page_config(page_title="Sitios | Omada WiFi User Portal", page_icon="🌐", layout="wide")
apply_theme()
settings = get_settings()
require_login(settings.session_timeout_minutes)

page_header("🌐", "Sitios del controlador", "Lista de sites disponibles en el controlador Omada configurado en este portal.")

if st.button("🔄 Refrescar"):
    clear_sites_cache()

try:
    sites = get_sites_cached()
except OmadaError as exc:
    st.error(f"No se pudo conectar con el controlador Omada: {exc}")
    st.stop()

if not sites:
    st.info("El controlador no tiene sitios disponibles, o la cuenta de servicio no tiene acceso a ninguno.")
    st.stop()

df = pd.DataFrame(sites)
preferred_cols = [c for c in ["name", "siteId", "region", "timeZone", "scenario"] if c in df.columns]
other_cols = [c for c in df.columns if c not in preferred_cols]
st.dataframe(df[preferred_cols + other_cols], use_container_width=True, hide_index=True)

st.metric("Total de sitios", len(sites))
