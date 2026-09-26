from __future__ import annotations

import threading
from pathlib import Path

import duckdb

_lock = threading.Lock()
_connection: "duckdb.DuckDBPyConnection | None" = None
_connected_path: "Path | None" = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS admins (
    id              VARCHAR PRIMARY KEY,
    username        VARCHAR UNIQUE NOT NULL,
    password_hash   VARCHAR NOT NULL,
    totp_secret     VARCHAR,
    mfa_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    role            VARCHAR NOT NULL DEFAULT 'operator',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT current_timestamp,
    last_login_at   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              VARCHAR PRIMARY KEY,
    ts              TIMESTAMP NOT NULL DEFAULT current_timestamp,
    admin_username  VARCHAR NOT NULL,
    action          VARCHAR NOT NULL,
    site_id         VARCHAR,
    site_name       VARCHAR,
    target_user     VARCHAR,
    status          VARCHAR NOT NULL,
    detail          VARCHAR
);
"""


def get_connection(db_path: Path) -> "duckdb.DuckDBPyConnection":
    """Devuelve una conexión DuckDB única por proceso (patrón singleton).

    DuckDB solo permite que un proceso escriba sobre un mismo archivo a la
    vez; para una app Streamlit (un proceso, múltiples hilos/sesiones) basta
    con una conexión compartida protegida por un lock. Si el proyecto
    necesita escalar a varias réplicas o procesos independientes, sustituye
    este módulo por un backend cliente-servidor (PostgreSQL, MySQL...)
    manteniendo la misma interfaz pública usada por AdminStore y AuditLog.
    """
    global _connection, _connected_path
    with _lock:
        db_path = Path(db_path)
        if _connection is None or _connected_path != db_path:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            _connection = duckdb.connect(str(db_path))
            _connection.execute(SCHEMA)
            _connected_path = db_path
        return _connection


def get_lock() -> threading.Lock:
    """Lock global compartido para serializar escrituras concurrentes."""
    return _lock
