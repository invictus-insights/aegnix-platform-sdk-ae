# make_keypair.py
from aegnix_core.crypto import ed25519_generate
from aegnix_core.utils import b64e
import base64

# Generate Ed25519 keypair
priv, pub = ed25519_generate()   # priv: bytes(32), pub: bytes(32)

# Encode both keys
priv_b64 = base64.b64encode(priv).decode()
pub_b64 = b64e(pub)

# Print / save
print("priv_b64:", priv_b64)
print("pub_b64:", pub_b64)