# aegnix_ae/client_v2.py
import os
import time
import base64
import logging
from typing import Optional, List, Dict, Any, Callable

import requests

from aegnix_core.envelope import Envelope
from aegnix_core.crypto import ed25519_sign, sign_envelope
from aegnix_core.transport import transport_factory
from aegnix_ae.decorators import EventRegistry
from aegnix_ae.session import SessionState, SessionStore

log = logging.getLogger(__name__)


class AEClientError(Exception):
    """Base AEClient error."""
    pass


class RegistrationError(AEClientError):
    """Raised when challenge/verify fails."""
    pass


class SessionError(AEClientError):
    """Raised when session/refresh operations fail."""
    pass


class AEClient:
    """
    AEClient v2 — Session-aware AE SDK (Phase 4B)
    ============================================

    Features:
      • Challenge-response registration with ABI
      • Access + refresh token handling
      • Optional automatic refresh + persistence
      • Transport abstraction (local / http / pubsub / etc.)
      • Declarative capabilities (publishes / subscribes)
      • Decorator-based event handler registry

    Modes (Option C):
      - Default: automatic (just works)
      - Advanced: manual session control

    Parameters
    ----------
    name : str
        Unique AE identifier. Used as "producer" and "sub" claim.
    abi_url : str, optional
        ABI Service base URL. Defaults to $ABI_URL or http://localhost:8080
    keypair : dict
        Must contain:
            "pub": str|bytes (public key, base64 or raw)
            "priv": str|bytes (private key, base64 or raw)
    transport : str or Transport, optional
        If str, sets AE_TRANSPORT and resolves via transport_factory().
    publishes : list[str], optional
        Subjects AE will emit.
    subscribes : list[str], optional
        Subjects AE will consume.
    session_store_path : str, optional
        JSON file to persist session. Defaults to ~/.aegnix/sessions/<name>.json
    auto_refresh : bool
        If True, AEClient will refresh access token lazily on emit() when expiring.
    auto_persist : bool
        If True, session is saved to disk after register/refresh.

    Advanced usage:
      - Set auto_refresh=False and call refresh_session() yourself.
      - Inject a custom Transport that knows how to use access_token.
    """

    def __init__(
        self,
        name: str,
        abi_url: Optional[str] = None,
        keypair: Optional[Dict[str, Any]] = None,
        transport: Optional[Any] = None,
        publishes: Optional[List[str]] = None,
        subscribes: Optional[List[str]] = None,
        session_store_path: Optional[str] = None,
        auto_refresh: bool = True,
        auto_persist: bool = True,
    ):
        self.name = name
        self.abi_url = abi_url or os.getenv("ABI_URL", "http://localhost:8080").rstrip("/")
        self.keypair = keypair or {}
        self.registry = EventRegistry()

        self.publishes = publishes or []
        self.subscribes = subscribes or []

        self.auto_refresh = auto_refresh
        self.auto_persist = auto_persist

        # Session
        if session_store_path is None:
            # ~/.aegnix/sessions/<name>.json
            default_dir = os.path.join(os.path.expanduser("~"), ".aegnix", "sessions")
            os.makedirs(default_dir, exist_ok=True)
            session_store_path = os.path.join(default_dir, f"{name}.json")
        self.session_store = SessionStore(session_store_path)
        self.session: Optional[SessionState] = None

        # --- Keypair validation & normalization
        self._validate_and_normalize_keypair()

        # --- Transport selection
        if isinstance(transport, str):
            os.environ["AE_TRANSPORT"] = transport
            os.environ["ABI_URL"] = self.abi_url
            self.transport = transport_factory()
        else:
            self.transport = transport or transport_factory()

        # Some transports (e.g. HTTP) may need base URL
        if hasattr(self.transport, "base_url"):
            self.transport.base_url = self.abi_url

    # ------------------------------------------------------------------
    # Keypair normalization
    # ------------------------------------------------------------------
    def _validate_and_normalize_keypair(self) -> None:
        if "pub" not in self.keypair or "priv" not in self.keypair:
            raise ValueError("AEClient requires keypair containing 'pub' and 'priv'")

        # Normalize priv key to raw bytes
        priv = self.keypair["priv"]
        if isinstance(priv, str):
            try:
                # assume base64
                priv = base64.b64decode(priv)
            except Exception:
                # if not base64, treat as raw utf-8
                priv = priv.encode("utf-8")
        self.keypair["priv"] = priv

        # Normalize pub key to base64 string (for key_id, metadata)
        pub = self.keypair["pub"]
        if isinstance(pub, bytes):
            pub_b64 = base64.b64encode(pub).decode()
        else:
            # assume pub already base64 string
            pub_b64 = pub
        self.keypair["pub_b64"] = pub_b64

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def _apply_session_to_transport(self) -> None:
        """
        Push current access_token into transport, if supported.

        We keep the old "set_grant" convention so existing transports
        keep working, but they are now given the access_token.
        """
        if not self.session:
            return

        if hasattr(self.transport, "set_grant"):
            self.transport.set_grant(self.session.access_token)
        elif hasattr(self.transport, "set_token"):
            self.transport.set_token(self.session.access_token)
        # else: transport may not require JWT (e.g. local bus)

    def _save_session_if_needed(self) -> None:
        if self.auto_persist and self.session:
            self.session_store.save(self.session)

    # ------------------------------------------------------------------
    # Public API: registration & lifecycle
    # ------------------------------------------------------------------
    def register_with_abi(self) -> bool:
        """
        Run full challenge–response registration and initialize session.

        This is the "fresh boot" path when an AE starts with no session
        or an expired/invalid session.
        """
        ae_id = self.name
        log.info(f"[{ae_id}] Starting ABI registration against {self.abi_url}")

        # 1) Request challenge
        r = requests.post(f"{self.abi_url}/register", json={"ae_id": ae_id})
        if not r.ok:
            raise RegistrationError(f"Challenge request failed: {r.status_code} {r.text}")
        payload = r.json()
        nonce_b64 = payload["nonce"]
        nonce = base64.b64decode(nonce_b64)

        # 2) Sign challenge (Ed25519)
        sig = ed25519_sign(self.keypair["priv"], nonce)
        sig_b64 = base64.b64encode(sig).decode()

        # 3) Verify with ABI
        vr = requests.post(
            f"{self.abi_url}/verify",
            json={"ae_id": ae_id, "signed_nonce_b64": sig_b64},
        )
        if not vr.ok:
            raise RegistrationError(f"Verification failed: {vr.status_code} {vr.text}")

        data = vr.json()
        if not data.get("verified"):
            raise RegistrationError(f"AE not verified: {data}")

        log.info({"event": "ae_verified", "ae_id": ae_id})

        # 4) Build session state from response
        self.session = SessionState.from_verify_response(ae_id=ae_id, data=data)
        self._apply_session_to_transport()
        self._save_session_if_needed()

        # 5) Declare capabilities, if configured
        if self.publishes or self.subscribes:
            try:
                self.declare_capabilities(self.publishes, self.subscribes)
            except Exception as e:
                log.error(f"[{ae_id}] Capability declaration failed: {e}")
        return True

    def resume_or_register(self) -> bool:
        """
        Try to resume a previous session from disk.

        If:
          - no session file, or
          - refresh token expired, or
          - refresh fails

        Then fall back to a full register_with_abi().
        """
        ae_id = self.name
        sess = self.session_store.load()
        if not sess:
            log.info(f"[{ae_id}] No existing session on disk; performing fresh registration")
            return self.register_with_abi()

        self.session = sess
        log.info(
            {
                "event": "session_resume",
                "ae_id": ae_id,
                "session_id": sess.session_id,
                "access_expired": sess.is_access_expired(),
                "refresh_expired": sess.is_refresh_expired(),
            }
        )

        if sess.is_refresh_expired(leeway=5):
            log.info(f"[{ae_id}] Refresh token expired; performing fresh registration")
            return self.register_with_abi()

        # Try refresh to ensure we have a live access token
        try:
            self.refresh_session()
            return True
        except Exception as e:
            log.warning(f"[{ae_id}] Failed to refresh existing session; re-registering: {e}")
            return self.register_with_abi()

    def refresh_session(self) -> None:
        """
        Explicit session refresh using /session/refresh.

        This is the manual control path used in advanced flows or when
        auto_refresh=False.
        """
        if not self.session:
            raise SessionError("No active session to refresh")

        if self.session.is_refresh_expired(leeway=0):
            raise SessionError("Refresh token expired; AE must re-register")

        body = {
            "session_id": self.session.session_id,
            "refresh_token": self.session.refresh_token,
        }
        r = requests.post(f"{self.abi_url}/session/refresh", json=body)
        if not r.ok:
            raise SessionError(f"Session refresh failed: {r.status_code} {r.text}")

        data = r.json()
        self.session = SessionState.from_refresh_response(
            ae_id=self.name,
            session_id=self.session.session_id,
            data=data,
        )
        log.info(
            {
                "event": "session_refreshed",
                "ae_id": self.name,
                "session_id": self.session.session_id,
            }
        )
        self._apply_session_to_transport()
        self._save_session_if_needed()

    def _ensure_access_token(self, leeway: int = 5) -> None:
        """
        Ensure we have a valid access token.

        If auto_refresh is enabled and token is expired/near-expiry,
        attempt a refresh automatically.
        """
        if not self.session:
            raise SessionError("AE has no active session; call register_with_abi()")

        if not self.session.is_access_expired(leeway=leeway):
            return

        if not self.auto_refresh:
            # manual-mode: caller must call refresh_session()
            raise SessionError("Access token expired; auto_refresh=False")

        log.info(f"[{self.name}] Access token expiring/expired; refreshing")
        self.refresh_session()

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------
    def emit(self, subject: str, payload: Dict[str, Any], labels: Optional[List[str]] = None) -> None:
        """
        Emit a signed envelope via the configured transport.

        Behavior:
          - Ensures a valid access token (refreshing if needed, if auto_refresh=True)
          - Signs the envelope with AE's Ed25519 keypair
          - Delegates actual publish to the Transport
        """
        # Ensure session/access token is good (if your transport needs it)
        self._ensure_access_token()

        env = Envelope.make(
            producer=self.name,
            subject=subject,
            payload=payload,
            labels=labels or ["default"],
            key_id=self.keypair["pub_b64"],
        )
        env = sign_envelope(env, self.keypair["priv"], env.key_id)
        self.transport.publish(subject, env.to_dict())

        log.debug(
            {
                "event": "emit",
                "ae_id": self.name,
                "subject": subject,
                "labels": labels or ["default"],
            }
        )

    # ------------------------------------------------------------------
    # Listener Registration / Subscriptions
    # ------------------------------------------------------------------
    def on(self, subject: str) -> Callable:
        """
        Decorator-based handler registration:
            @ae.on("fusion.topic")
            def handle(msg): ...

        Stored in self.registry.handlers.
        """
        return self.registry.on(subject)

    def listen(self) -> None:
        """
        Bind AE handlers to the transport.

        NOTE:
          For HTTP transports that map to ABI /subscribe/<topic>, the
          transport implementation is responsible for:
            - Passing Authorization: Bearer <access_token>
            - Handling reconnects / heartbeat

          AEClient ensures transport has the latest access_token via
          _apply_session_to_transport().
        """
        self._ensure_access_token()
        for subject, handler in self.registry.handlers.items():
            self.transport.subscribe(subject, handler)
        log.info(f"[{self.name}] listening for subscribed subjects: {list(self.registry.handlers.keys())}")

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def declare_capabilities(
        self,
        publishes: Optional[List[str]] = None,
        subscribes: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Declare AE capabilities to ABI using /ae/capabilities.

        Requires:
          - self.session populated
          - Valid access_token
        """
        if not self.session:
            raise SessionError("AE must have a session before declaring capabilities")

        self._ensure_access_token()

        publishes = publishes or []
        subscribes = subscribes or []
        meta = meta or {}

        headers = {
            "Authorization": f"Bearer {self.session.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "publishes": publishes,
            "subscribes": subscribes,
            "meta": meta,
        }

        url = f"{self.abi_url}/ae/capabilities"
        r = requests.post(url, json=payload, headers=headers)
        if not r.ok:
            raise AEClientError(f"Capability declaration failed: {r.status_code} {r.text}")

        resp = r.json()
        log.info(
            {
                "event": "capabilities_declared",
                "ae_id": self.name,
                "publishes": publishes,
                "subscribes": subscribes,
            }
        )
        return resp
