"""CLI para crear administradores del portal (el primero, o adicionales sin
pasar por la pantalla de "Administración").

Uso:
    python scripts/create_first_admin.py
"""
from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.admin_store import AdminStore  # noqa: E402
from config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    store = AdminStore(settings.app_db_path)

    print("== Alta de administrador — Omada WiFi User Portal ==")
    username = input("Usuario: ").strip()
    if not username:
        print("El usuario no puede estar vacío.")
        sys.exit(1)

    if store.get_by_username(username):
        print(f"Ya existe un administrador con el usuario '{username}'.")
        sys.exit(1)

    password = getpass("Contraseña: ")
    password_confirm = getpass("Confirma la contraseña: ")
    if password != password_confirm:
        print("Las contraseñas no coinciden.")
        sys.exit(1)
    if len(password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    role = "superadmin" if store.count() == 0 else "operator"
    admin = store.create(username, password, role=role)
    print(f"\nAdministrador '{admin.username}' creado con rol '{admin.role}'.")
    print("La verificación en dos pasos (MFA) se configura automáticamente en su primer login en el portal.")


if __name__ == "__main__":
    main()
