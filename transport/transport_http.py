# aegnix_ae/transport/transport_http.py
import requests
from aegnix_core.logger import get_logger

log = get_logger("AE.Transport.HTTP")

class HTTPAdapter:
    """HTTP transport adapter for posting envelopes to ABI /emit endpoint."""
    def __init__(self, base_url: str):
        # self.base_url = base_url.rstrip("/")
        self.base_url = base_url
        self.handlers = {}

    def publish(self, subject: str, message: dict):
        """POST a signed envelope to the ABI /emit endpoint."""
        url = f"{self.base_url}/emit"
        log.debug(f"[HTTP PUB] → {url} | subject={subject}")
        try:
            res = requests.post(url, json=message, timeout=5)
            if res.ok:
                log.info(f"[HTTP PUB] {res.status_code} {res.reason}")
                return res.json()
            else:
                log.error(f"[HTTP PUB] {res.status_code}: {res.text}")
                return {"error": res.text, "status": res.status_code}
        except Exception as e:
            log.exception(f"[HTTP PUB] Exception: {e}")
            return {"error": str(e)}

    def subscribe(self, subject: str, handler):
        """No-op in HTTP mode — placeholder for future event streaming."""
        self.handlers[subject] = handler
        log.debug(f"[HTTP SUB] Registered handler for subject '{subject}' (noop)")
