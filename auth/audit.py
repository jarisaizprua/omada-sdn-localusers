from __future__ import annotations

import uuid
from pathlib import Path

from db.database import get_connection, get_lock


class AuditLog:
    """Registro de acciones administrativas (login, alta/edición/baja de
    usuarios WiFi, cambios de administradores) para trazabilidad."""

    def __init__(self, db_path: Path):
        self._conn = get_connection(db_path)
        self._lock = get_lock()

    def record(
        self,
        admin_username: str,
        action: str,
        status: str,
        *,
        site_id: str = "",
        site_name: str = "",
        target_user: str = "",
        detail: str = "",
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit_log "
                "(id, admin_username, action, site_id, site_name, target_user, status, detail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [str(uuid.uuid4()), admin_username, action, site_id, site_name, target_user, status, detail],
            )

    def recent(self, limit: int = 200) -> list[tuple]:
        with self._lock:
            return self._conn.execute(
                "SELECT ts, admin_username, action, site_name, target_user, status, detail "
                "FROM audit_log ORDER BY ts DESC LIMIT ?",
                [limit],
            ).fetchall()
