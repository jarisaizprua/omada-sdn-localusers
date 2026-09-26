from __future__ import annotations

import time

import streamlit as st

SESSION_KEYS = ("authenticated", "admin_username", "admin_role", "admin_id", "login_ts")


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


def current_admin() -> dict:
    return {
        "id": st.session_state.get("admin_id"),
        "username": st.session_state.get("admin_username"),
        "role": st.session_state.get("admin_role"),
    }


def log_in(admin_id: str, username: str, role: str) -> None:
    st.session_state["authenticated"] = True
    st.session_state["admin_id"] = admin_id
    st.session_state["admin_username"] = username
    st.session_state["admin_role"] = role
    st.session_state["login_ts"] = time.time()


def log_out() -> None:
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)


def require_login(session_timeout_minutes: int = 30) -> dict:
    """Detiene la ejecución de la página si no hay una sesión de admin válida."""
    if not is_authenticated():
        st.warning("Debes iniciar sesión para acceder a esta página.")
        st.page_link("app.py", label="Ir a inicio de sesión", icon="🔐")
        st.stop()

    elapsed_minutes = (time.time() - st.session_state.get("login_ts", 0)) / 60
    if elapsed_minutes > session_timeout_minutes:
        log_out()
        st.warning("Tu sesión expiró por inactividad. Vuelve a iniciar sesión.")
        st.page_link("app.py", label="Ir a inicio de sesión", icon="🔐")
        st.stop()

    return current_admin()


def require_role(*allowed_roles: str) -> dict:
    admin = require_login()
    if admin["role"] not in allowed_roles:
        st.error("No tienes permisos suficientes para ver esta página.")
        st.stop()
    return admin
