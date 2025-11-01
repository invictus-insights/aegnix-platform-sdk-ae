import logging
from aegnix_core.envelope import Envelope
from aegnix_core.crypto import ed25519_sign
from aegnix_ae.transport.transport_gcp_pubsub import GcpPubSubAdapter
from aegnix_ae.decorators import EventRegistry

log = logging.getLogger(__name__)

class AEClient:
    def __init__(self, name, abi_url, keypair, transport=None):
        self.name = name
        self.abi_url = abi_url
        self.keypair = keypair
        self.transport = transport or GcpPubSubAdapter()
        self.registry = EventRegistry()
        self.session_grant = None

    def register_with_abi(self):
        """Simulate ABI handshake and obtain a short-lived session grant."""
        log.debug(f"[{self.name}] initiating who_is_there handshake with {self.abi_url}")
        # TODO: Replace with actual ABI request
        self.session_grant = {"grant": "mock-grant"}
        log.info(f"[{self.name}] registered successfully with ABI")
        return True

    def emit(self, subject, payload, labels=None):
        """Emit signed message to swarm."""
        env = Envelope.make(
            producer=self.name,
            subject=subject,
            payload=payload,
            labels=labels or ["default"],
            key_id=self.keypair["pub"]
        )
        env.sig = ed25519_sign(env.to_bytes(), self.keypair["priv"])
        # self.transport.publish(subject, env.to_json())
        self.transport.publish(subject, env.to_dict())
        log.debug(f"[{self.name}] emitted message on subject '{subject}'")

    def listen(self):
        """Start listening to registered subjects."""
        log.info(f"[{self.name}] listening for subscribed subjects…")
        for subject, handler in self.registry.handlers.items():
            self.transport.subscribe(subject, handler)
