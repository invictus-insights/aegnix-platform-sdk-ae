# aegnix_ae/session.py
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class SessionState:
    """
    Client-side view of an ABI session.

    This mirrors the /verify and /session/refresh responses:

        {
          "session_id": "...",
          "access_token": "...",
          "expires_in": 300,
          "refresh_token": "...",
          "refresh_expires_in": 86400
        }
    """

    ae_id: str
    session_id: str
    access_token: str
    access_expires_at: int
    refresh_token: str
    refresh_expires_at: int

    @classmethod
    def from_verify_response(cls, ae_id: str, data: Dict[str, Any]) -> "SessionState":
        now = int(time.time())
        return cls(
            ae_id=ae_id,
            session_id=data["session_id"],
            access_token=data["access_token"],
            access_expires_at=now + int(data.get("expires_in", 0)),
            refresh_token=data["refresh_token"],
            refresh_expires_at=now + int(data.get("refresh_expires_in", 0)),
        )

    @classmethod
    def from_refresh_response(
        cls, ae_id: str, session_id: str, data: Dict[str, Any]
    ) -> "SessionState":
        now = int(time.time())
        return cls(
            ae_id=ae_id,
            session_id=session_id,
            access_token=data["access_token"],
            access_expires_at=now + int(data.get("expires_in", 0)),
            refresh_token=data["refresh_token"],
            refresh_expires_at=now + int(data.get("refresh_expires_in", 0)),
        )

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "SessionState":
        return cls(**raw)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # ------------------------------
    # Expiration helpers
    # ------------------------------
    def is_access_expired(self, leeway: int = 0) -> bool:
        now = int(time.time())
        return now >= (self.access_expires_at - leeway)

    def is_refresh_expired(self, leeway: int = 0) -> bool:
        now = int(time.time())
        return now >= (self.refresh_expires_at - leeway)


class SessionStore:
    """
    Simple JSON file-backed session store.

    Phase 4B: plaintext JSON with path-based isolation.
    Later: add encryption (Fernet) or OS keyring.

    Default path example:
        ~/.aegnix/sessions/<ae_name>.json
    """

    def __init__(self, path: Optional[str] = None):
        if path is None:
            base = Path.home() / ".aegnix" / "sessions"
            base.mkdir(parents=True, exist_ok=True)
            self.path = base / "session.json"
        else:
            self.path = Path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Optional[SessionState]:
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            return SessionState.from_dict(raw)
        except Exception as e:
            log.warning(f"[SessionStore] Failed to load session from {self.path}: {e}")
            return None

    def save(self, session: SessionState) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f)
            log.debug(f"[SessionStore] Session saved to {self.path}")
        except Exception as e:
            log.error(f"[SessionStore] Failed to save session: {e}")

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
                log.debug(f"[SessionStore] Session cleared at {self.path}")
        except Exception as e:
            log.error(f"[SessionStore] Failed to clear session: {e}")
