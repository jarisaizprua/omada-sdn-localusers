from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from db.database import get_connection, get_lock

from . import security


@dataclass
class Admin:
    id: str
    username: str
    password_hash: str
    totp_secret: Optional[str]
    mfa_enabled: bool
    role: str
    is_active: bool


def _row_to_admin(row) -> Admin:
    return Admin(
        id=row[0],
        username=row[1],
        password_hash=row[2],
        totp_secret=row[3],
        mfa_enabled=row[4],
        role=row[5],
        is_active=row[6],
    )


_ADMIN_COLUMNS = "id, username, password_hash, totp_secret, mfa_enabled, role, is_active"


class AdminStore:
    """Repositorio de administradores del portal.

    Mantiene una interfaz simple (get / create / update) para que, si el
    proyecto crece y necesita otro motor de base de datos (PostgreSQL,
    etc.), solo haya que reescribir esta clase sin tocar las páginas de
    Streamlit que la usan.
    """

    def __init__(self, db_path: Path):
        self._conn = get_connection(db_path)
        self._lock = get_lock()

    def get_by_username(self, username: str) -> Optional[Admin]:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_ADMIN_COLUMNS} FROM admins WHERE username = ?", [username]
            ).fetchone()
        return _row_to_admin(row) if row else None

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT count(*) FROM admins").fetchone()[0]

    def list_all(self) -> list[Admin]:
        with self._lock:
            rows = self._conn.execute(f"SELECT {_ADMIN_COLUMNS} FROM admins ORDER BY username").fetchall()
        return [_row_to_admin(r) for r in rows]

    def create(self, username: str, plain_password: str, role: str = "operator") -> Admin:
        admin_id = str(uuid.uuid4())
        password_hash = security.hash_password(plain_password)
        with self._lock:
            self._conn.execute(
                "INSERT INTO admins (id, username, password_hash, role) VALUES (?, ?, ?, ?)",
                [admin_id, username, password_hash, role],
            )
        return Admin(admin_id, username, password_hash, None, False, role, True)

    def set_totp_secret(self, admin_id: str, secret: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE admins SET totp_secret = ?, mfa_enabled = TRUE WHERE id = ?", [secret, admin_id]
            )

    def reset_mfa(self, admin_id: str) -> None:
        """Borra el secreto TOTP del administrador. En su próximo login se le
        pedirá escanear un código QR nuevo (útil si perdió el dispositivo
        con su app de autenticación)."""
        with self._lock:
            self._conn.execute(
                "UPDATE admins SET totp_secret = NULL, mfa_enabled = FALSE WHERE id = ?", [admin_id]
            )

    def set_active(self, admin_id: str, is_active: bool) -> None:
        with self._lock:
            self._conn.execute("UPDATE admins SET is_active = ? WHERE id = ?", [is_active, admin_id])

    def set_password(self, admin_id: str, plain_password: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE admins SET password_hash = ? WHERE id = ?",
                [security.hash_password(plain_password), admin_id],
            )

    def touch_last_login(self, admin_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE admins SET last_login_at = current_timestamp WHERE id = ?", [admin_id]
            )
