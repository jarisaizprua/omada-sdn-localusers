"""CLI para resetear la contraseña de un administrador del portal.

No toca el MFA: si el admin ya tenía la verificación en dos pasos activada,
la sigue pidiendo al iniciar sesión con la nueva contraseña.

Uso:
    python scripts/reset_admin_password.py
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

    print("== Resetear contraseña de administrador — Omada WiFi User Portal ==")

    admins = store.list_all()
    if not admins:
        print("No hay administradores registrados todavía. Usa create_first_admin.py.")
        sys.exit(1)

    print("\nAdministradores existentes:")
    for a in admins:
        estado = "activo" if a.is_active else "INACTIVO"
        print(f"  - {a.username} ({a.role}, {estado})")

    username = input("\nUsuario al que le vas a cambiar la contraseña: ").strip()
    admin = store.get_by_username(username)
    if not admin:
        print(f"No existe ningún administrador con el usuario '{username}'.")
        sys.exit(1)

    new_password = getpass("Nueva contraseña: ")
    confirm = getpass("Confirma la nueva contraseña: ")
    if new_password != confirm:
        print("Las contraseñas no coinciden.")
        sys.exit(1)
    if len(new_password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    store.set_password(admin.id, new_password)
    print(f"\nContraseña de '{admin.username}' actualizada correctamente.")
    if admin.mfa_enabled:
        print("El MFA sigue activo: seguirá pidiendo el código de tu app de autenticación al entrar.")


if __name__ == "__main__":
    main()
