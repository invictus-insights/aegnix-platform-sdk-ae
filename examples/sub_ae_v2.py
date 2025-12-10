# sub_ae_v2.py
from aegnix_core.utils import b64d

from aegnix_ae.client_v2 import AEClient

ABI_URL = "http://localhost:8080"

PRIV = b64d("...your priv...")
PUB_B64 = "..."

ae = AEClient(
    name="sub_ae",
    abi_url=ABI_URL,
    keypair={"priv": PRIV, "pub": PUB_B64},
    subscribes=["hello.world"],
    transport="http",
)

ae.resume_or_register()


@ae.on("hello.world")
def handle_hello(msg):
    print("Received hello.world →", msg)


ae.listen()
