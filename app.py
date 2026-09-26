from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from auth import security, totp
from auth.admin_store import AdminStore
from auth.audit import AuditLog
from auth.session_guard import current_admin, is_authenticated, log_in, log_out
from config import get_settings
from utils.logging_config import configure_logging
from utils.ui import apply_theme, page_header

st.set_page_config(page_title="Omada WiFi User Portal", page_icon="📶", layout="wide")
apply_theme()

settings = get_settings()
configure_logging(settings.log_level)

admin_store = AdminStore(settings.app_db_path)
audit = AuditLog(settings.app_db_path)


def _login_form() -> None:
    page_header("📶", "Omada WiFi User Portal", "Administración de usuarios locales de WiFi para controladores Omada SDN.")

    if admin_store.count() == 0:
        st.info(
            "Todavía no hay administradores registrados. Crea el primero desde una terminal con:\n\n"
            "```\npython scripts/create_first_admin.py\n```"
        )
        return

    col_left, col_center, col_right = st.columns([1, 1.3, 1])
    with col_center:
        st.subheader("Iniciar sesión")
        st.session_state.setdefault("login_stage", "credentials")
        stage = st.session_state["login_stage"]

        if stage == "credentials":
            _credentials_step()
        elif stage == "mfa_setup":
            _mfa_enrollment_step()
        elif stage == "mfa_verify":
            _mfa_verification_step()


def _credentials_step() -> None:
    attempts = st.session_state.get("login_attempts", 0)
    if attempts >= settings.max_login_attempts:
        st.error("Demasiados intentos fallidos. Recarga la página en unos minutos e inténtalo de nuevo.")
        return

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Continuar", use_container_width=True)

    if not submitted:
        return

    admin = admin_store.get_by_username(username.strip())
    if not admin or not admin.is_active or not security.verify_password(password, admin.password_hash):
        st.session_state["login_attempts"] = attempts + 1
        audit.record(username or "?", "LOGIN", "ERROR", detail="Usuario o contraseña incorrectos")
        st.error("Usuario o contraseña incorrectos.")
        return

    st.session_state["login_attempts"] = 0
    st.session_state["pending_admin"] = {"id": admin.id, "username": admin.username, "role": admin.role}
    st.session_state["login_stage"] = "mfa_setup" if not admin.mfa_enabled else "mfa_verify"
    st.rerun()


def _mfa_enrollment_step() -> None:
    pending = st.session_state["pending_admin"]
    st.subheader("Configura la verificación en dos pasos (obligatoria)")
    st.write(
        "Escanea este código QR con una app de autenticación "
        "(Google Authenticator, Microsoft Authenticator, Authy, 1Password, etc.) "
        "para completar tu primer inicio de sesión."
    )

    st.session_state.setdefault("new_totp_secret", totp.generate_secret())
    secret = st.session_state["new_totp_secret"]
    uri = totp.provisioning_uri(secret, pending["username"])

    st.image(totp.qr_code_png_bytes(uri), width=220)
    with st.expander("¿No puedes escanear el QR? Introduce la clave manualmente"):
        st.code(secret)

    with st.form("mfa_setup_form"):
        code = st.text_input("Código de 6 dígitos de tu app de autenticación")
        confirmed = st.form_submit_button("Confirmar y activar MFA", use_container_width=True)

    if confirmed:
        if totp.verify_code(secret, code):
            admin_store.set_totp_secret(pending["id"], secret)
            admin_store.touch_last_login(pending["id"])
            audit.record(pending["username"], "LOGIN", "OK", detail="Primer login + activación de MFA")
            log_in(pending["id"], pending["username"], pending["role"])
            _clear_login_flow_state()
            st.rerun()
        else:
            st.error("Código incorrecto. Verifica la hora de tu dispositivo e inténtalo de nuevo.")

    if st.button("Cancelar"):
        _clear_login_flow_state()
        st.rerun()


def _mfa_verification_step() -> None:
    pending = st.session_state["pending_admin"]
    st.subheader("Verificación en dos pasos")
    st.write(f"Hola **{pending['username']}**, introduce el código de tu app de autenticación.")

    with st.form("mfa_verify_form"):
        code = st.text_input("Código de 6 dígitos")
        submitted = st.form_submit_button("Entrar", use_container_width=True)

    if submitted:
        admin = admin_store.get_by_username(pending["username"])
        if admin and totp.verify_code(admin.totp_secret, code):
            admin_store.touch_last_login(admin.id)
            audit.record(admin.username, "LOGIN", "OK", detail="Login con MFA correcto")
            log_in(admin.id, admin.username, admin.role)
            _clear_login_flow_state()
            st.rerun()
        else:
            audit.record(pending["username"], "LOGIN", "ERROR", detail="Código MFA incorrecto")
            st.error("Código incorrecto.")

    if st.button("Cancelar"):
        _clear_login_flow_state()
        st.rerun()


def _clear_login_flow_state() -> None:
    for key in ("login_stage", "pending_admin", "new_totp_secret"):
        st.session_state.pop(key, None)


def _home_dashboard() -> None:
    admin = current_admin()
    page_header("📶", "Omada WiFi User Portal")
    st.success(f"Sesión iniciada como **{admin['username']}** ({admin['role']})")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.page_link("pages/1_Sitios.py", label="Ver sitios", icon="🌐")
    with col2:
        st.page_link("pages/2_Usuarios.py", label="Gestionar usuarios WiFi", icon="👥")
    with col3:
        if admin["role"] == "superadmin":
            st.page_link("pages/3_Administracion.py", label="Administración del portal", icon="🛡️")

    st.divider()
    if st.button("Cerrar sesión"):
        audit.record(admin["username"], "LOGOUT", "OK")
        log_out()
        st.rerun()


if is_authenticated():
    _home_dashboard()
else:
    _login_form()
