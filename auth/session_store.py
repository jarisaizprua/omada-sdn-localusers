from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from db.database import get_connection, get_lock

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portal_sessions (
    token       VARCHAR PRIMARY KEY,
    admin_id    VARCHAR NOT NULL,
    username    VARCHAR NOT NULL,
    role        VARCHAR NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT current_timestamp,
    expires_at  TIMESTAMP NOT NULL
)
"""


@dataclass
class PersistedSession:
    token: str
    admin_id: str
    username: str
    role: str
    expires_at: datetime


class SessionStore:
    """Sesiones de administrador persistidas en DuckDB, identificadas por un
    token aleatorio que viaja en la URL (?session=...). Permiten que un
    refresh del navegador no obligue a volver a iniciar sesión (usuario +
    contraseña + MFA) mientras el token siga vigente.

    La ventana de vigencia es deslizante: cada vez que se restaura una
    sesión desde el token, su expiración se extiende otra vez
    `ttl_minutes` hacia adelante (ver touch())."""

    def __init__(self, db_path: Path):
        self._conn = get_connection(db_path)
        self._lock = get_lock()
        with self._lock:
            self._conn.execute(_SCHEMA)

    def create(self, admin_id: str, username: str, role: str, ttl_minutes: int) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
        with self._lock:
            self._conn.execute(
                "INSERT INTO portal_sessions (token, admin_id, username, role, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [token, admin_id, username, role, expires_at],
            )
        return token

    def get(self, token: str) -> Optional[PersistedSession]:
        if not token:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT token, admin_id, username, role, expires_at FROM portal_sessions WHERE token = ?",
                [token],
            ).fetchone()
        if not row:
            return None
        session = PersistedSession(token=row[0], admin_id=row[1], username=row[2], role=row[3], expires_at=row[4])
        if session.expires_at < datetime.now():
            self.delete(token)
            return None
        return session

    def touch(self, token: str, ttl_minutes: int) -> None:
        """Extiende la expiración (ventana deslizante) al restaurar la sesión."""
        new_expiry = datetime.now() + timedelta(minutes=ttl_minutes)
        with self._lock:
            self._conn.execute("UPDATE portal_sessions SET expires_at = ? WHERE token = ?", [new_expiry, token])

    def delete(self, token: str) -> None:
        if not token:
            return
        with self._lock:
            self._conn.execute("DELETE FROM portal_sessions WHERE token = ?", [token])

    def delete_expired(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM portal_sessions WHERE expires_at < current_timestamp")
