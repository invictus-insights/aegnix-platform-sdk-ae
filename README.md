# AEGNIX AE SDK

Atomic Expert (AE) Software Development Kit 
This SDK allows individual Atomic Experts to register with an ABI service, emit signed messages, and communicate through pluggable transports (local, GCP Pub/Sub, etc.).

---

## Overview

The **AE SDK** provides a lightweight client interface (`AEClient`) and transport adapters for message emission, subscription, and trust validation through the ABI handshake.

### Core Features

* **AEClient** — Register with ABI, emit signed envelopes, and subscribe to topics.
* **Envelope** — Shared message format (imported from `aegnix_core`).
* **LocalAdapter** — In-memory Pub/Sub adapter for offline and unit testing.
* **Mocked crypto** — For local test runs, real signing can be replaced with a mock signature.

---

## Directory Structure

```
aegnix_sdk/
├── aegnix_ae/
│   ├── __init__.py
│   ├── client.py
│   └── transport/
│       ├── __init__.py
│       ├── transport_local.py
│       └── transport_base.py
└── tests/
    ├── test_ae_sdk.py
    └── test_abi_sdk.py
```

---

## Installation

> Ensure the `aegnix_core` package is installed in **editable** mode first:

```bash
cd ../aegnix_core
pip install -e .
```

Then install the AE SDK:

```bash
cd ../aegnix_sdk
pip install -e .
```

This enables local editing and development across both packages.

---

## Running Tests

Run all AE + ABI SDK integration tests with debug logging:

```bash
pytest -v -s --log-cli-level=DEBUG
```

Expected output for AE SDK test (`test_ae_register_and_emit`):

```
INFO     aegnix_ae.transport.transport_local: [LOCAL SUB] Subscribed to fusion.topic
DEBUG    aegnix_ae.client: [fusion_ae] initiating who_is_there handshake with http://localhost:8080
INFO     aegnix_ae.client: [fusion_ae] registered successfully with ABI
INFO     aegnix_ae.transport.transport_local: [LOCAL PUB] fusion.topic: {"track_id": "ABC123"}...
INFO     root: [HANDLER] Received: {"track_id": "ABC123"}
DEBUG    aegnix_ae.client: [fusion_ae] emitted message on subject 'fusion.topic'
PASSED
```

All tests passing confirms a full local handshake and signed envelope emission using the **LocalAdapter**.

---

## How It Works

1. **AEClient.register_with_abi()** simulates the ABI dual-crypto handshake.
2. **AEClient.emit()** creates a signed `Envelope` and publishes via the transport.
3. **LocalAdapter** routes the message in-memory, invoking any subscribed handlers.

---

## Developer Notes

* Local transport is used for offline testing — no Google Cloud credentials required.
* Real-world deployment will use `transport_gcp_pubsub.py` (GCP) or `transport_kafka.py`.
* The signing process uses `aegnix_core.crypto.ed25519_sign`; in tests it’s monkeypatched to a mock.

---

## Phase 1 Definition of Done

* Two toy AEs exchange a signed message through local transport.
* ABI SDK successfully admits/denies and persists keyring in SQLite.
* Signed audit records are produced.
* Tests fully pass under `pytest -v -s --log-cli-level=DEBUG`.

---

## Next Steps

**Phase 2** — Extend transports (GCP Pub/Sub → Kafka → NATS)
**Phase 3** — Integrate distributed policy enforcement and live ABI verification

---

**Repository:** `github.com/invictus-insights/aegnix_ae_sdk`
**Author:** Invictus Insights R&D
**Version:** 0.1.0
**License:** Proprietary (pending patent filing)
