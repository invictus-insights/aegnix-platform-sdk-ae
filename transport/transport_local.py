import logging
from aegnix_ae.transport.transport_base import BaseTransport

log = logging.getLogger(__name__)

class LocalAdapter(BaseTransport):
    """Simple in-memory adapter for offline development and testing."""
    def __init__(self):
        self.handlers = {}

    def publish(self, subject, message):
        log.info(f"[LOCAL PUB] {subject}: {str(message)[:60]}...")
        if subject in self.handlers:
            for handler in self.handlers[subject]:
                handler(message)

    def subscribe(self, subject, handler):
        log.info(f"[LOCAL SUB] Subscribed to {subject}")
        self.handlers.setdefault(subject, []).append(handler)
