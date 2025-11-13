# AEGNIX AE SDK

The **AEGNIX AE SDK** empowers developers to create autonomous Atomic Experts (AEs) — micro-agents capable of reasoning, emitting signed intelligence, and participating securely within the AEGNIX swarm mesh (“the war”).

Each AE can self-register with an Agent Bridge Interface (ABI), authenticate via a dual-crypto handshake, and communicate through modular transports (Local / GCP Pub/Sub / Kafka). 
It serves as the agentic runtime layer for the AEGNIX ecosystem enabling trusted, verifiable collaboration among distributed AEs operating across tactical, enterprise, or defense domains.
---

## Overview

| Component              | Description                                                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **AEClient**           | Handles registration (`who_is_there` handshake), signed emissions, and topic subscriptions.                        |
| **Envelope**           | Shared signed message format from `aegnix_core`.                                                                   |
| **Transport Adapters** | Pluggable backends: `LocalAdapter` for offline tests, `PubSubAdapter` (coming Phase 3F), `KafkaAdapter` (Phase 4). |
| **Mock Crypto**        | Enables deterministic unit testing without real keys.                                                              |

---

## 🧬 Directory Structure

```
aegnix_sdk/
    ├── aegnix_ae
    ├── README.md
    ├── __init__.py
    ├── client.py
    ├── decorators.py
    ├── make_keypair.py
    ├── pyproject.toml
    └── transport
        ├── __init__.py
        ├── transport_base.py
        ├── transport_gcp_pubsub.py
        ├── transport_http.py
        ├── transport_kafka.py
        └── transport_local.py
    
```

---

## Installation

Install the **core** dependency:

```bash
cd ../aegnix_core
pip install -e .
```

 Install the **AE SDK** in editable mode:

```bash
cd ../aegnix_sdk/aegnix_ae
pip install -e .
```

 Verify installation:

```bash
pip list | grep aegnix
# aegnix-core 0.3.6
# aegnix-sdk  0.3.6
```

---

## Running Tests

Run all AE + ABI SDK integration tests with full logs:

```bash
pytest -v -s --log-cli-level=DEBUG tests/test_ae_sdk.py 

```

Expected output (Phase 3E stable):

```
tests/test_ae_sdk.py .....                                                                                 [100%]
```

Confirms successful handshake, signed envelope emission, and message loopback via LocalAdapter.

> `/emit` JWT verification tests will arrive in Phase 3F.

---

## How It Works

1. **AEClient.register_with_abi()** performs the dual-crypto admission handshake.
2. **AEClient.emit()** signs an `Envelope` and sends via the selected transport.
3. **LocalAdapter** delivers in-memory for fast dev + CI testing.
4. **Policy + Audit** enforcement handled by ABI Service.

---

## Developer Notes

* Default transport → `LocalAdapter` (offline-safe).
* Real deployments → `transport_gcp_pubsub.py` → `transport_kafka.py`.
* Uses `aegnix_core.crypto.ed25519_sign`; tests monkeypatch mock signing.
* Works seamlessly with **ABI Service v0.3.6** (Phase 3E “All Green”).

---

## Definition of Done (Phase 3E)

* [x] AEClient registration and emit via LocalAdapter
* [x] End-to-end ABI handshake verified
* [x] Signed Envelope schema stable
* [x] Integration tests (AE ↔ ABI) passing
* [ ] JWT grant + `/emit` verification (Phase 3F)

---

## Next Steps

**Phase 3F** — JWT issuance + verified `/emit` pipeline
**Phase 4** — Kafka adapter + distributed policy replication
**Phase 5** — Multi-AE swarms / UIX integration / confidence loops

---

**Repository:** `github.com/invictus-insights/aegnix_ae_sdk`
**Author:** Invictus Insights R&D
**Version:** 0.3.6 (Phase 3E All Green)
**License:** Proprietary / Pending Patent Filing
