from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from auth.audit import AuditLog
from auth.session_guard import require_login
from config import get_settings
from omada_client.exceptions import OmadaAPIError, OmadaError
from omada_client.users import (
    LocalUserInput,
    create_local_user,
    delete_local_user,
    find_user_by_username,
    update_local_user,
)
from services.omada_service import (
    clear_local_users_cache,
    get_local_users_cached,
    get_omada_client,
    get_sites_cached,
)
from utils.ui import apply_theme, page_header

st.set_page_config(page_title="Usuarios WiFi | Omada WiFi User Portal", page_icon="👥", layout="wide")
apply_theme()
settings = get_settings()
admin = require_login(settings.session_timeout_minutes)
audit = AuditLog(settings.app_db_path)

page_header(
    "👥",
    "Usuarios locales de WiFi",
    "Crea, edita y elimina usuarios locales (hotspot) que se autentican en el portal cautivo del WiFi, "
    "en uno o varios sitios a la vez.",
)


def _format_expiration(expiration_time_ms) -> tuple[str, "int | None"]:
    """Convierte expirationTime (epoch ms) a fecha legible + días restantes."""
    if not expiration_time_ms:
        return "-", None
    try:
        dt = datetime.fromtimestamp(int(expiration_time_ms) / 1000)
    except (TypeError, ValueError, OSError):
        return "-", None
    days_left = (dt.date() - datetime.now().date()).days
    return dt.strftime("%d/%m/%Y %H:%M"), days_left


def _days_left_label(days_left) -> str:
    if days_left is None:
        return "-"
    if days_left < 0:
        return f"Expirado hace {abs(days_left)} día(s)"
    if days_left == 0:
        return "Expira hoy"
    return f"{days_left} día(s)"

try:
    sites = get_sites_cached()
except OmadaError as exc:
    st.error(f"No se pudo conectar con el controlador Omada: {exc}")
    st.stop()

if not sites:
    st.warning("No hay sitios disponibles.")
    st.stop()

site_options = {s["name"]: s["siteId"] for s in sites}
client = get_omada_client()

tab_list, tab_create, tab_edit, tab_delete = st.tabs(
    ["📋 Listado", "➕ Crear usuario", "✏️ Editar usuario", "🗑️ Eliminar usuario"]
)

# ---------------------------------------------------------------- LISTADO --
with tab_list:
    selected_names = st.multiselect(
        "Sitio(s) a consultar",
        options=list(site_options.keys()),
        default=list(site_options.keys())[:1],
        key="list_sites",
    )
    search = st.text_input("Buscar por usuario o nombre", key="list_search")

    col_query, col_refresh = st.columns([3, 1])
    query_clicked = col_query.button("Consultar", key="list_query")
    if col_refresh.button("🔄 Forzar actualización", key="list_force_refresh"):
        clear_local_users_cache()
        query_clicked = True

    if query_clicked:
        rows = []
        with st.spinner("Consultando usuarios..."):
            for name in selected_names:
                site_id = site_options[name]
                try:
                    for u in get_local_users_cached(site_id):
                        fecha_exp, dias_exp = _format_expiration(u.get("expirationTime"))
                        rows.append(
                            {
                                "Sitio": name,
                                "Usuario": u.get("userName"),
                                "Nombre": u.get("name") or "-",
                                "Fecha de expiración": fecha_exp,
                                "Días restantes": _days_left_label(dias_exp),
                                "Habilitado": u.get("enable"),
                                "MAC": u.get("macAddress") or "-",
                                "Dispositivos simultáneos": u.get("maxUsers"),
                            }
                        )
                except OmadaAPIError as exc:
                    st.warning(f"{name}: {exc}")

        if not rows:
            st.info("No se encontraron usuarios locales con esos criterios.")
        else:
            df = pd.DataFrame(rows)
            if search:
                mask = df["Usuario"].str.contains(search, case=False, na=False) | df["Nombre"].str.contains(
                    search, case=False, na=False
                )
                df = df[mask]
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Habilitado": st.column_config.CheckboxColumn("Habilitado", disabled=True),
                    "Dispositivos simultáneos": st.column_config.NumberColumn("Dispositivos simultáneos"),
                },
            )
            st.caption(f"{len(df)} usuario(s) encontrados.")

# ----------------------------------------------------------------- CREAR --
with tab_create:
    target_names = st.multiselect(
        "Crear en el/los siguiente(s) sitio(s)", options=list(site_options.keys()), key="create_sites"
    )

    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            user_name = st.text_input("Usuario (userName)")
            display_name = st.text_input("Nombre para mostrar")
            phone = st.text_input("Teléfono (opcional)")
        with col2:
            password = st.text_input("Contraseña WiFi", type="password")
            max_users = st.number_input("Máximo de dispositivos simultáneos", min_value=1, max_value=64, value=1)
            expiration_days = st.number_input(
                "Expira en (días, 0 = fin del año en curso, como en la interfaz de Omada)",
                min_value=0, max_value=3650, value=0
            )
        enable = st.checkbox("Habilitado", value=True)

        with st.expander("Opciones avanzadas"):
            adv_col1, adv_col2 = st.columns(2)
            with adv_col1:
                down_limit = st.number_input("Límite de bajada (Kbps, 0 = sin límite)", min_value=0, value=0)
                mac_address = st.text_input("Vincular a MAC (opcional)")
            with adv_col2:
                up_limit = st.number_input("Límite de subida (Kbps, 0 = sin límite)", min_value=0, value=0)
                binding_type = st.selectbox(
                    "Tipo de vínculo (binding)",
                    options=[0, 1, 2],
                    format_func=lambda v: {0: "Sin vínculo", 1: "Vínculo estático", 2: "Vínculo dinámico"}[v],
                )

        submitted = st.form_submit_button("Crear usuario", use_container_width=True, type="primary")

    if submitted:
        if not target_names:
            st.error("Selecciona al menos un sitio.")
        elif not user_name or not password:
            st.error("Usuario y contraseña son obligatorios.")
        else:
            payload = LocalUserInput(
                user_name=user_name.strip(),
                password=password,
                display_name=display_name.strip(),
                phone=phone.strip(),
                enable=enable,
                max_users=int(max_users),
                expiration_days=int(expiration_days),
                binding_type=int(binding_type),
                mac_address=mac_address.strip(),
                down_limit_kbps=int(down_limit),
                up_limit_kbps=int(up_limit),
            )

            results = []
            with st.spinner("Creando usuario en los sitios seleccionados..."):
                for name in target_names:
                    site_id = site_options[name]
                    try:
                        create_local_user(client, site_id, payload)
                        clear_local_users_cache(site_id)
                        results.append((name, "OK", ""))
                        audit.record(
                            admin["username"], "CREATE_USER", "OK",
                            site_id=site_id, site_name=name, target_user=user_name,
                        )
                    except OmadaAPIError as exc:
                        results.append((name, "ERROR", str(exc)))
                        audit.record(
                            admin["username"], "CREATE_USER", "ERROR",
                            site_id=site_id, site_name=name, target_user=user_name, detail=str(exc),
                        )

            st.dataframe(
                pd.DataFrame(results, columns=["Sitio", "Resultado", "Detalle"]),
                use_container_width=True, hide_index=True,
            )

# ----------------------------------------------------------------- EDITAR --
with tab_edit:
    edit_site_name = st.selectbox("Sitio", options=list(site_options.keys()), key="edit_site")
    edit_site_id = site_options[edit_site_name]

    if st.button("Cargar usuarios de este sitio", key="edit_load"):
        with st.spinner("Cargando..."):
            st.session_state["edit_users_cache"] = get_local_users_cached(edit_site_id)

    users_cache = st.session_state.get("edit_users_cache", [])
    if users_cache:
        usernames = [u.get("userName") for u in users_cache]
        chosen = st.selectbox("Usuario a editar", options=usernames, key="edit_chosen_user")
        current = next((u for u in users_cache if u.get("userName") == chosen), None)

        also_other_sites = st.multiselect(
            "También aplicar los mismos cambios (si existe el mismo usuario) en:",
            options=[n for n in site_options if n != edit_site_name],
            key="edit_other_sites",
        )

        if current:
            with st.form("edit_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_password = st.text_input(
                        "Nueva contraseña (obligatoria: la API requiere reenviarla en cada actualización)",
                        type="password",
                    )
                    new_display_name = st.text_input("Nombre para mostrar", value=current.get("name", ""))
                    new_phone = st.text_input("Teléfono", value=current.get("phone", ""))
                with col2:
                    new_enable = st.checkbox("Habilitado", value=bool(current.get("enable", True)))
                    new_max_users = st.number_input(
                        "Máximo de dispositivos simultáneos",
                        min_value=1, max_value=64, value=int(current.get("maxUsers") or 1),
                    )
                    new_expiration_days = st.number_input(
                        "Expira en (días desde ahora, 0 = fin del año en curso, como en la interfaz de Omada)",
                        min_value=0, max_value=3650, value=0
                    )
                submitted_edit = st.form_submit_button("Guardar cambios", use_container_width=True, type="primary")

            if submitted_edit:
                if not new_password:
                    st.error("Introduce la contraseña (se reenvía en cada actualización según la API).")
                else:
                    payload = LocalUserInput(
                        user_name=chosen,
                        password=new_password,
                        display_name=new_display_name.strip(),
                        phone=new_phone.strip(),
                        enable=new_enable,
                        max_users=int(new_max_users),
                        expiration_days=int(new_expiration_days),
                        mac_address=current.get("macAddress", "") or "",
                        binding_type=int(current.get("bindingType") or 0),
                    )

                    targets = [(edit_site_name, edit_site_id, current.get("id"))]
                    for other_name in also_other_sites:
                        other_id = site_options[other_name]
                        other_user = find_user_by_username(client, other_id, chosen)
                        if other_user:
                            targets.append((other_name, other_id, other_user.get("id")))

                    results = []
                    with st.spinner("Guardando cambios..."):
                        for name, site_id, user_id in targets:
                            try:
                                update_local_user(client, site_id, user_id, payload)
                                clear_local_users_cache(site_id)
                                results.append((name, "OK", ""))
                                audit.record(
                                    admin["username"], "UPDATE_USER", "OK",
                                    site_id=site_id, site_name=name, target_user=chosen,
                                )
                            except OmadaAPIError as exc:
                                results.append((name, "ERROR", str(exc)))
                                audit.record(
                                    admin["username"], "UPDATE_USER", "ERROR",
                                    site_id=site_id, site_name=name, target_user=chosen, detail=str(exc),
                                )

                    st.dataframe(
                        pd.DataFrame(results, columns=["Sitio", "Resultado", "Detalle"]),
                        use_container_width=True, hide_index=True,
                    )
    else:
        st.info("Pulsa 'Cargar usuarios de este sitio' para empezar.")

# --------------------------------------------------------------- ELIMINAR --
with tab_delete:
    del_target_names = st.multiselect(
        "Eliminar de el/los siguiente(s) sitio(s)", options=list(site_options.keys()), key="delete_sites"
    )
    del_username = st.text_input("Usuario (userName) a eliminar", key="delete_username")
    confirm = st.checkbox("Confirmo que quiero eliminar este usuario de forma permanente", key="delete_confirm")

    if st.button("Eliminar usuario", type="primary", key="delete_button"):
        if not del_target_names or not del_username:
            st.error("Selecciona al menos un sitio e indica el usuario.")
        elif not confirm:
            st.error("Debes confirmar la eliminación.")
        else:
            results = []
            with st.spinner("Eliminando..."):
                for name in del_target_names:
                    site_id = site_options[name]
                    try:
                        found = find_user_by_username(client, site_id, del_username.strip())
                        if not found:
                            results.append((name, "OMITIDO", "El usuario no existe en este sitio"))
                            continue
                        delete_local_user(client, site_id, found["id"])
                        clear_local_users_cache(site_id)
                        results.append((name, "OK", ""))
                        audit.record(
                            admin["username"], "DELETE_USER", "OK",
                            site_id=site_id, site_name=name, target_user=del_username,
                        )
                    except OmadaAPIError as exc:
                        results.append((name, "ERROR", str(exc)))
                        audit.record(
                            admin["username"], "DELETE_USER", "ERROR",
                            site_id=site_id, site_name=name, target_user=del_username, detail=str(exc),
                        )

            st.dataframe(
                pd.DataFrame(results, columns=["Sitio", "Resultado", "Detalle"]),
                use_container_width=True, hide_index=True,
            )
