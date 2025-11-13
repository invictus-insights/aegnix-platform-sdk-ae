import requests, base64, logging, os
from aegnix_core.envelope import Envelope
from aegnix_core.crypto import ed25519_sign, sign_envelope
from aegnix_ae.transport import transport_factory
from aegnix_ae.decorators import EventRegistry

log = logging.getLogger(__name__)

class AEClient:
    """
      AEClient
      --------
      Atomic Expert client for secure registration and message emission
      within the AEGNIX mesh.

      • Uses Ed25519 for challenge–response and envelope signing.
      • Maintains transport abstraction (HTTP, Pub/Sub, Local).
      • All signing follows canonical order: ed25519_sign(priv_raw, data).
      """
    def __init__(self, name, abi_url=None, keypair=None, transport=None):
        self.name = name
        self.abi_url = abi_url or os.getenv("ABI_URL", "http://localhost:8080")
        self.keypair = keypair
        # self.transport = transport or transport_factory()
        self.registry = EventRegistry()
        self.session_grant = None

        if isinstance(transport, str):
            os.environ["AE_TRANSPORT"] = transport  # so factory picks it up
            self.transport = transport_factory()

        else:
            self.transport = transport or transport_factory()

        # Ensure pub_b64 convenience key
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
        nonce = base64.b64decode(nonce_b64)

        # Step 2: Sign challenge

        # sig = ed25519_sign(nonce, self.keypair["priv"])
        sig = ed25519_sign(self.keypair["priv"], nonce)
        sig_b64 = base64.b64encode(sig).decode()

        # Step 3: Verify signature with ABI
        verify_res = requests.post(f"{self.abi_url}/verify", json={
            "ae_id": ae_id,
            "signed_nonce_b64": sig_b64
        })
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
            return True

        # if data.get("verified") and data.get("grant"):
        #     self.session_grant = data["grant"]
        #     # surface to HTTPAdapter via env for now (simple)
        #     os.environ["AE_GRANT"] = self.session_grant
        #     return True
        return False
        # self.session_grant = data if data.get("verified") else None
        # return bool(self.session_grant)

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
            key_id=self.keypair["pub"]
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
