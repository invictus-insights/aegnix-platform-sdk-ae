# aegnix_ae/transport/__init__.py
import os
from aegnix_ae.transport.transport_local import LocalAdapter
from aegnix_ae.transport.transport_http import HTTPAdapter
from aegnix_ae.transport.transport_gcp_pubsub import GcpPubSubAdapter

def transport_factory():
    """Return best-fit transport adapter based on environment or config."""
    mode = os.getenv("AE_TRANSPORT", "local").lower()
    if mode == "gcp":
        return GcpPubSubAdapter()
    elif mode == "http":
        base_url = os.getenv("ABI_URL", "http://localhost:8080")
        return HTTPAdapter(base_url)
    else:
        return LocalAdapter()
