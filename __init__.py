# __init__.py
"""
AEGNIX AE SDK
----------------
Agent Expert SDK for secure communication with the AEGNIX ABI.

This package provides:
  • AEClient (registration + emission)
  • Envelope signing utilities
  • Transport abstraction
  • Local and distributed event handling
"""

from .client_v2 import AEClient

__all__ = ["AEClient"]
__version__ = "0.9.2-phase-4b"
