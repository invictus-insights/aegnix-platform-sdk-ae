# aegnix_ae/transport/transport_http.py
import requests, json, threading, os
from aegnix_core.logger import get_logger

log = get_logger("AE.Transport.HTTP")

class HTTPAdapter:
    """
    HTTP transport adapter for posting envelopes to the ABI /emit endpoint.

    Features:
    - Supports Bearer JWT authentication via AE_GRANT environment variable.
    - Supports SSE-based subscription for live topic streaming (Phase 3E).
    """
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.handlers = {}
        self._threads = []

    # ------------------------------------------------------------------
    # Outbound publishing
    # ------------------------------------------------------------------
    def publish(self, subject: str, message: dict):
        """
        POST a signed envelope to the ABI /emit endpoint.
        Adds an Authorization header automatically if AE_GRANT is set.
        """
        url = f"{self.base_url}/emit"
        headers = {"Content-Type": "application/json"}

        # Bearer grant (session token from AEClient.register_with_abi)
        grant = os.getenv("AE_GRANT")
        if grant:
            headers["Authorization"] = f"Bearer {grant}"

        log.debug(f"[HTTP PUB] → {url} | subject={subject}")
        try:
            res = requests.post(url, json=message, headers=headers, timeout=5)
            if res.ok:
                log.info(f"[HTTP PUB] {res.status_code} {res.reason}")
                return res.json()
            else:
                log.error(f"[HTTP PUB] {res.status_code}: {res.text}")
                return {"error": res.text, "status": res.status_code}
        except Exception as e:
            log.exception(f"[HTTP PUB] Exception: {e}")
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Inbound streaming (Server-Sent Events)
    # ------------------------------------------------------------------
    def _sse_reader(self, topic: str, handler):
        """
        Background SSE reader thread. Connects to /subscribe/{topic}
        and passes each incoming JSON payload to the provided handler.
        """
        url = f"{self.base_url}/subscribe/{topic}"
        log.info(f"[HTTP SUB] Connecting to SSE stream: {url}")
        try:
            with requests.get(url, stream=True, timeout=None) as r:
                for line in r.iter_lines():
                    if not line:
                        continue
                    if line.startswith(b"data:"):
                        try:
                            payload = json.loads(line[len(b"data:"):].strip().decode())
                            handler(payload)
                        except Exception as e:
                            log.error(f"[SSE parse error] {e}")
        except Exception as e:
            log.error(f"[SSE connection error] {e}")

    def subscribe(self, subject: str, handler):
        """
        Subscribe to a topic stream via SSE (Server-Sent Events).

        Spawns a background thread that listens for messages from
        /subscribe/{subject} and invokes the handler on each one.
        """
        self.handlers[subject] = handler
        log.info(f"[HTTP SUB] Subscribing to {subject}")
        t = threading.Thread(target=self._sse_reader, args=(subject, handler), daemon=True)
        t.start()
        self._threads.append(t)

# # aegnix_ae/transport/transport_http.py
# import requests
# from aegnix_core.logger import get_logger
#
# log = get_logger("AE.Transport.HTTP")
#
# class HTTPAdapter:
#     """HTTP transport adapter for posting envelopes to ABI /emit endpoint."""
#     def __init__(self, base_url: str):
#         # self.base_url = base_url.rstrip("/")
#         self.base_url = base_url
#         self.handlers = {}
#
#     def publish(self, subject: str, message: dict):
#         """POST a signed envelope to the ABI /emit endpoint."""
#         url = f"{self.base_url}/emit"
#         log.debug(f"[HTTP PUB] → {url} | subject={subject}")
#         try:
#             res = requests.post(url, json=message, timeout=5)
#             if res.ok:
#                 log.info(f"[HTTP PUB] {res.status_code} {res.reason}")
#                 return res.json()
#             else:
#                 log.error(f"[HTTP PUB] {res.status_code}: {res.text}")
#                 return {"error": res.text, "status": res.status_code}
#         except Exception as e:
#             log.exception(f"[HTTP PUB] Exception: {e}")
#             return {"error": str(e)}
#
#     def subscribe(self, subject: str, handler):
#         """No-op in HTTP mode — placeholder for future event streaming."""
#         self.handlers[subject] = handler
#         log.debug(f"[HTTP SUB] Registered handler for subject '{subject}' (noop)")
