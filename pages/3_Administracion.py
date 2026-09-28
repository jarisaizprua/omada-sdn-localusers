from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from auth.admin_store import AdminStore
from auth.audit import AuditLog
from auth.session_guard import require_role
from config import get_settings
from utils.ui import page_header

settings = get_settings()
admin = require_role("superadmin", session_timeout_minutes=settings.session_timeout_minutes)

store = AdminStore(settings.app_db_path)
audit = AuditLog(settings.app_db_path)

page_header("🛡️", "Administración del portal")

tab_admins, tab_audit, tab_conn = st.tabs(["Administradores", "Registro de auditoría", "Conexión Omada"])

# ------------------------------------------------------------- ADMINS --
with tab_admins:
    st.subheader("Administradores del portal")
    admins = store.list_all()
    df = pd.DataFrame(
        [
            {"Usuario": a.username, "Rol": a.role, "MFA activo": a.mfa_enabled, "Activo": a.is_active}
            for a in admins
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Crear nuevo administrador")
    with st.form("new_admin_form"):
        new_username = st.text_input("Usuario")
        new_password = st.text_input("Contraseña temporal", type="password")
        new_role = st.selectbox("Rol", options=["operator", "superadmin"])
        submitted = st.form_submit_button("Crear")

    if submitted:
        if not new_username or len(new_password) < 8:
            st.error("Usuario obligatorio y contraseña de al menos 8 caracteres.")
        elif store.get_by_username(new_username):
            st.error("Ese usuario ya existe.")
        else:
            store.create(new_username, new_password, role=new_role)
            audit.record(admin["username"], "CREATE_ADMIN", "OK", target_user=new_username)
            st.success(
                f"Administrador '{new_username}' creado. Configurará su MFA (código QR) "
                "en su primer inicio de sesión en el portal."
            )
            st.rerun()

    st.divider()
    st.subheader("Activar / desactivar administrador")
    other_admins = [a.username for a in admins if a.username != admin["username"]]
    if other_admins:
        target = st.selectbox("Administrador", options=other_admins)
        target_admin = store.get_by_username(target)
        new_state = st.toggle("Activo", value=target_admin.is_active)
        if st.button("Aplicar"):
            store.set_active(target_admin.id, new_state)
            audit.record(
                admin["username"], "TOGGLE_ADMIN", "OK", target_user=target, detail=f"is_active={new_state}"
            )
            st.success("Actualizado.")
            st.rerun()
    else:
        st.caption("No hay otros administradores todavía.")

# -------------------------------------------------------------- AUDIT --
with tab_audit:
    st.subheader("Últimas 200 acciones registradas")
    rows = audit.recent(200)
    df_audit = pd.DataFrame(
        rows, columns=["Fecha", "Admin", "Acción", "Sitio", "Usuario objetivo", "Resultado", "Detalle"]
    )
    st.dataframe(df_audit, use_container_width=True, hide_index=True)

# --------------------------------------------------------- CONEXIÓN --
with tab_conn:
    st.subheader("Configuración de conexión al controlador Omada")
    st.caption("Solo lectura. Para cambiar estos valores edita el archivo .env y reinicia la aplicación.")
    masked_client_id = settings.omada_client_id[:4] + "*" * max(len(settings.omada_client_id) - 4, 0)
    st.code(
        f"OMADA_BASE_URL (Interface Access Address) = {settings.omada_base_url}\n"
        f"OMADA_OMADAC_ID (Omada ID)                = {settings.omada_omadac_id}\n"
        f"OMADA_CLIENT_ID                            = {masked_client_id}\n"
        f"OMADA_VERIFY_SSL                            = {settings.omada_verify_ssl}\n"
        f"OAuth Login Page Address (solo informativo) = {settings.omada_oauth_login_page_address or '(no configurado)'}\n",
        language="bash",
    )
