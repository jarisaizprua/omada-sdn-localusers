"""CLI para resetear la verificación en dos pasos (MFA/TOTP) de un
administrador del portal — por ejemplo, si perdió el teléfono con su app de
autenticación y ya no puede generar códigos.

No toca su contraseña. Tras el reset, en su próximo login se le pedirá
escanear un código QR nuevo (pantalla de enrolamiento automática).

Uso:
    python scripts/reset_admin_mfa.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.admin_store import AdminStore  # noqa: E402
from config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    store = AdminStore(settings.app_db_path)

    print("== Resetear MFA de administrador — Omada WiFi User Portal ==")

    admins = store.list_all()
    if not admins:
        print("No hay administradores registrados todavía. Usa create_first_admin.py.")
        sys.exit(1)

    print("\nAdministradores existentes:")
    for a in admins:
        mfa = "MFA activo" if a.mfa_enabled else "MFA no configurado"
        print(f"  - {a.username} ({a.role}, {mfa})")

    username = input("\nUsuario al que le vas a resetear el MFA: ").strip()
    admin = store.get_by_username(username)
    if not admin:
        print(f"No existe ningún administrador con el usuario '{username}'.")
        sys.exit(1)

    if not admin.mfa_enabled:
        print(f"'{admin.username}' todavía no tiene MFA configurado. No hay nada que resetear.")
        sys.exit(0)

    confirm = input(f"¿Confirmas que quieres borrar el MFA de '{admin.username}'? (escribe 'si'): ").strip().lower()
    if confirm != "si":
        print("Cancelado.")
        sys.exit(0)

    store.reset_mfa(admin.id)
    print(f"\nMFA de '{admin.username}' reseteado. En su próximo login se le pedirá escanear un QR nuevo.")


if __name__ == "__main__":
    main()
