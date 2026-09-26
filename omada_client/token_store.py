from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional, TypedDict


class TokenData(TypedDict):
    access_token: str
    refresh_token: str
    token_type: str
    obtained_at: float
    expires_at: float          # epoch seconds en que expira el access_token
    refresh_expires_at: float  # epoch seconds en que expira el refresh_token


class TokenStore:
    """Persiste el access/refresh token en disco para no repetir el flujo de
    login completo en cada reinicio del proceso.

    Un solo archivo JSON por instalación, protegido con un lock en memoria
    (varias sesiones de Streamlit comparten el mismo proceso Python).
    """

    _lock = threading.Lock()

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Optional[TokenData]:
        with self._lock:
            if not self.path.exists():
                return None
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None

    def save(self, data: TokenData) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
