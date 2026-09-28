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
from auth.session_store import SessionStore
from config import get_settings
from utils.logging_config import configure_logging
from utils.ui import apply_theme, page_header

st.set_page_config(page_title="Omada WiFi User Portal", page_icon="📶", layout="wide")
apply_theme()

settings = get_settings()
configure_logging(settings.log_level)

admin_store = AdminStore(settings.app_db_path)
audit = AuditLog(settings.app_db_path)
session_store = SessionStore(settings.app_db_path)


def _start_persisted_session(admin_id: str, username: str, role: str) -> None:
    """Crea un token de sesión persistido y lo pone en la URL, para que un
    refresh del navegador no obligue a volver a iniciar sesión."""
    token = session_store.create(admin_id, username, role, ttl_minutes=settings.session_timeout_minutes)
    st.query_params["session"] = token


def _end_persisted_session() -> None:
    token = st.query_params.get("session")
    if token:
        session_store.delete(token)
    st.query_params.clear()


def _restore_session_from_token() -> None:
    """Si el navegador trae ?session=... en la URL (típicamente tras un
    refresh) y todavía no hay sesión activa en este session_state, intenta
    restaurarla desde la base de datos."""
    if is_authenticated():
        return
    token = st.query_params.get("session")
    if not token:
        return
    persisted = session_store.get(token)
    if persisted is None:
        st.query_params.clear()  # token inválido/expirado: limpia la URL
        return
    session_store.touch(token, ttl_minutes=settings.session_timeout_minutes)
    log_in(persisted.admin_id, persisted.username, persisted.role)


_restore_session_from_token()


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
            _start_persisted_session(pending["id"], pending["username"], pending["role"])
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
            _start_persisted_session(admin.id, admin.username, admin.role)
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

    st.write("")
    cards = [
        ("🌐", "Sitios", "Consulta los sites disponibles en tu controlador Omada.", "pages/1_Sitios.py"),
        ("👥", "Usuarios WiFi", "Crea, edita y elimina usuarios locales en uno o varios sitios.", "pages/2_Usuarios.py"),
    ]
    if admin["role"] == "superadmin":
        cards.append(
            ("🛡️", "Administración", "Gestiona administradores del portal y revisa la auditoría.", "pages/3_Administracion.py")
        )

    cols = st.columns(len(cards))
    for col, (icon, title, desc, target) in zip(cols, cards):
        with col:
            with st.container(border=True):
                st.markdown(
                    f'<div class="omp-nav-card-icon">{icon}</div>'
                    f'<div class="omp-nav-card-title">{title}</div>'
                    f'<div class="omp-nav-card-desc">{desc}</div>',
                    unsafe_allow_html=True,
                )
                st.write("")
                st.page_link(target, label="Abrir →")

    st.write("")
    st.divider()
    if st.button("Cerrar sesión"):
        audit.record(admin["username"], "LOGOUT", "OK")
        _end_persisted_session()
        log_out()
        st.rerun()


# --------------------------------------------------------------------------
# Enrutamiento: usa la API moderna de Streamlit (st.navigation + st.Page) en
# vez de la autodetección de la carpeta pages/, para poder:
#   - dar títulos e íconos propios a cada página (en vez del nombre crudo
#     del archivo, ej. "app" en vez de "Inicio")
#   - ocultar el menú lateral por completo en la pantalla de login
#   - mostrar un logo real arriba del menú (st.logo)
# --------------------------------------------------------------------------
if not is_authenticated():
    pg = st.navigation([st.Page(_login_form, title="Iniciar sesión")], position="hidden")
else:
    admin = current_admin()
    pages = [
        st.Page(_home_dashboard, title="Inicio", icon="🏠", default=True),
        st.Page("pages/1_Sitios.py", title="Sitios", icon="🌐"),
        st.Page("pages/2_Usuarios.py", title="Usuarios WiFi", icon="👥"),
    ]
    if admin["role"] == "superadmin":
        pages.append(st.Page("pages/3_Administracion.py", title="Administración", icon="🛡️"))
    pg = st.navigation(pages)
    st.logo("assets/logo.svg", icon_image="assets/logo.svg")

pg.run()
