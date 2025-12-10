# client.py
import logging
import os

import requests
from aegnix_core.crypto import ed25519_sign, sign_envelope
from aegnix_core.envelope import Envelope
from aegnix_core.transport import transport_factory
from aegnix_core.utils import b64d, b64e

from aegnix_ae.decorators import EventRegistry

log = logging.getLogger(__name__)


class AEClient:
    """
    AEClient
    ========

    High-level client for building and running Agent Experts (AEs)
    within the AEGNIX distributed mesh.

    This class provides:

      • Ed25519 challenge-response registration with ABI
      • Automatic JWT session grant handling
      • Optional capability declaration (publish/subscribe sets)
      • Canonical envelope creation and signing
      • Transport abstraction (HTTP, Pub/Sub, Local)
      • Simple handler registry for inbound events

    Parameters
    ----------
    name : str
        Unique AE identifier. Becomes the "producer" field for emitted events.
    abi_url : str, optional
        Base URL of the ABI service. Defaults to environment variable
        ``ABI_URL`` or ``http://localhost:8080``.
    keypair : dict
        Must contain ``pub`` and ``priv`` keys (raw or base64).
        Optionally may include:
            • ``pub_b64``  – convenience cached base64 of pub
    transport : str or Transport instance, optional
        Transport layer used for publish/subscribe.
        If a string is passed, it is forwarded to ``AE_TRANSPORT`` and a
        transport is resolved via `transport_factory()`.
    publishes : list[str], optional
        Subjects this AE intends to emit. If provided, these are automatically
        declared to ABI after successful registration.
    subscribes : list[str], optional
        Subjects this AE intends to subscribe to. Also declared automatically.

    Attributes
    ----------
    session_grant : str or None
        JWT issued by ABI after challenge–response registration.
    registry : EventRegistry
        Registry of event handlers for inbound subjects.
    transport : Transport
        Resolved transport instance used for publish/subscribe.

    Usage Example
    -------------
    >>> keypair = {"pub": "...", "priv": "..."}
    >>> ae = AEClient(
    ...     name="fusion_ae",
    ...     keypair=keypair,
    ...     publishes=["fusion.emit"],
    ...     subscribes=["roe.result"]
    ... )
    >>> ae.register_with_abi()
    True
    >>> ae.emit("fusion.emit", {"value": 42})
    """

    def __init__(
        self,
        name,
        abi_url=None,
        keypair=None,
        transport=None,
        publishes=None,
        subscribes=None,
    ):
        self.name = name
        self.abi_url = abi_url or os.getenv("ABI_URL", "http://localhost:8080")
        self.keypair = keypair
        self.registry = EventRegistry()
        self.session_grant = None
        self.publishes = publishes or []
        self.subscribes = subscribes or []

        # --- Keypair validation
        if not self.keypair or "pub" not in self.keypair or "priv" not in self.keypair:
            raise ValueError("AEClient requires keypair containing 'pub' and 'priv'")

        # --- Transport selection ---
        if isinstance(transport, str):
            os.environ["AE_TRANSPORT"] = transport

            os.environ["ABI_URL"] = self.abi_url

            self.transport = transport_factory()

        else:
            self.transport = transport or transport_factory()

        if hasattr(self.transport, "base_url"):
            self.transport.base_url = self.abi_url.rstrip("/")

        # --- Ensure pub_b64 convenience key ---
        self.keypair.setdefault("pub_b64", self.keypair.get("pub"))

    # ------------------------------------------------------------------
    # Challenge–Response Registration
    # ------------------------------------------------------------------
    def register_with_abi(self):
        """Perform challenge–response registration."""
        log.debug(f"[{self.name}] initiating registration with {self.abi_url}")
        ae_id = self.name

        # Step 1: Request challenge
        res = requests.post(f"{self.abi_url}/register", json={"ae_id": ae_id})
        if not res.ok:
            raise Exception(f"Challenge request failed: {res.text}")
        # nonce_b64 = res.json()["nonce"]
        nonce_b64 = res.json()["nonce"]
        nonce = b64d(nonce_b64)

        # Step 2: Sign challenge

        # sig = ed25519_sign(nonce, self.keypair["priv"])
        sig = ed25519_sign(self.keypair["priv"], nonce)
        sig_b64 = b64e(sig).decode()

        # Step 3: Verify signature with ABI
        verify_res = requests.post(
            f"{self.abi_url}/verify", json={"ae_id": ae_id, "signed_nonce_b64": sig_b64}
        )
        if not verify_res.ok:
            raise Exception(f"Verification failed: {verify_res.text}")

        data = verify_res.json()
        log.info(f"[{self.name}] verification result: {data}")

        # Step 4: Capture grant
        verified = data.get("verified")
        grant = data.get("grant")

        if verified and grant:
            self.session_grant = grant
            # os.environ["AE_GRANT"] = grant
            if hasattr(self.transport, "set_grant"):
                self.transport.set_grant(grant)

            if self.publishes or self.subscribes:
                self.declare_capabilities(self.publishes, self.subscribes)
            return True

        return False

    # ------------------------------------------------------------------
    # Message Emission
    # ------------------------------------------------------------------
    def emit(self, subject, payload, labels=None):
        """Emit signed message to swarm."""
        env = Envelope.make(
            producer=self.name,
            subject=subject,
            payload=payload,
            labels=labels or ["default"],
            key_id=self.keypair["pub"],
        )
        # Canonical signing helper
        env = sign_envelope(env, self.keypair["priv"], env.key_id)

        # env.sig = ed25519_sign(env.to_bytes(), self.keypair["priv"])
        # self.transport.publish(subject, env.to_json())

        self.transport.publish(subject, env.to_dict())
        log.debug(f"[{self.name}] emitted message on subject '{subject}'")

    # ------------------------------------------------------------------
    # Listener Registration
    # ------------------------------------------------------------------
    def listen(self):
        """Start listening to registered subjects."""
        log.info(f"[{self.name}] listening for subscribed subjects…")
        for subject, handler in self.registry.handlers.items():
            self.transport.subscribe(subject, handler)

    # ------------------------------------------------------------
    # Shorthand handler registration
    # ------------------------------------------------------------
    def on(self, subject):
        """
        Convenience alias so AE code can use @ae.on("<subject>")
        instead of @ae.registry.on("<subject>").
        """
        return self.registry.on(subject)

    # ------------------------------------------------------------
    # Capability Declaration
    # ------------------------------------------------------------
    def declare_capabilities(self, publishes=None, subscribes=None, meta=None):
        """
        Declare AE capabilities to ABI.

        Requires:
            - successful registration
            - session_grant containing valid JWT

        Args:
            publishes: list of subjects the AE wants to emit
            subscribes: list of subjects the AE wants to listen to
            meta: optional metadata for ABI or tooling

        Returns:
            dict: ABI response {status, ae_id, capability}
        """
        if not self.session_grant:
            raise Exception("AE must register_with_abi() before declaring capabilities")

        publishes = publishes or []
        subscribes = subscribes or []
        meta = meta or {}

        headers = {
            "Authorization": f"Bearer {self.session_grant}",
            "Content-Type": "application/json",
        }

        payload = {"publishes": publishes, "subscribes": subscribes, "meta": meta}

        url = f"{self.abi_url}/ae/capabilities"
        res = requests.post(url, json=payload, headers=headers)

        if not res.ok:
            raise Exception(
                f"Capability declaration failed ({res.status_code}): {res.text}"
            )

        data = res.json()
        log.info(
            {
                "event": "capabilities_declared",
                "publishes": publishes,
                "subscribes": subscribes,
            }
        )

        return data
