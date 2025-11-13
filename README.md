# AEGNIX ABI Service

The **AEGNIX Agent Bridge Interface (ABI) Service** is the secure admission and coordination layer for the **AEGNIX Swarm Mesh**. It governs how *Atomic Experts (AEs)* authenticate, publish, subscribe, and interoperate within trusted agentic networks.

It provides cryptographic admission control, event bus routing, live streaming via Server-Sent Events (SSE)/WebSocket, and policy-based message authorization — serving as the **central nervous system** for AEGNIX operations.

---

## Overview

| Component   | Description                                                                              |
| ----------- | ---------------------------------------------------------------------------------------- |
| **main.py** | FastAPI entrypoint — loads routes, initializes Keyring, Policy, and Admission modules.   |
| **bus.py**  | In-memory async EventBus with pub/sub and decorator-based message routing.               |
| **routes/** | Contains all API route handlers for registration, emission, audit, and SSE subscription. |
| **db/**     | SQLite state storage (keyring, trust records).                                           |
| **logs/**   | Centralized logs for ABI service and audit events.                                       |
| **tests/**  | Pytest suite covering registration, emit validation, and bus-to-SSE loopback.            |

---

## Key Modules

### Admission Service (`aegnix_abi.admission`)

Handles the dual-crypto handshake (`who_is_there`) for AEs joining the swarm:

1. Issues nonce challenges.
2. Verifies signed responses.
3. Updates keyring trust status.

### Keyring (`aegnix_abi.keyring`)

Stores and manages AE public keys, trust states, and revocation in SQLite.

### Policy Engine (`aegnix_abi.policy`)

Controls which subjects and labels an AE can publish or subscribe to.

### Audit Logger (`aegnix_abi.audit`)

Writes signed event envelopes to log files or Pub/Sub for non-repudiation.

### Event Bus (`bus.py`)

Lightweight async bus bridging internal modules, enabling:

* `bus.publish(topic, message)` → In-memory fan-out
* Decorator-style subscriptions via `@bus.subscribe("topic")`

### SSE Bridge (`routes/subscribe.py`)

Implements `/subscribe/{topic}` endpoint for real-time event streaming to AE developers.
Validated under **Phase 3E** with loopback tests ensuring bus → SSE continuity.

---

## Directory Structure

```
abi_service/
├── main.py                # FastAPI application entrypoint
├── bus.py                 # In-memory event bus
├── routes/                # Modular route handlers
│   ├── admin.py
│   ├── audit.py
│   ├── emit.py
│   ├── register.py
│   └── subscribe.py
├── db/                    # Persistent keyring storage
│   └── abi_state.db
├── logs/                  # Service + audit logs
│   ├── abi_service.log
│   └── abi_audit.log
└── tests/                 # Full test suite
    ├── test_register_flow.py
    ├── test_emit_signature.py
    └── test_subscribe_loopback.py
```

---

## Running Tests

Run all tests locally (ABI + SSE + Policy):

```bash
pytest -v -s --log-cli-level=DEBUG tests/

```

Expected output (Phase 3E verified):

```
============================================================
3 passed, 0 failed, all-green
============================================================
```

---

## Developer Notes

* Default storage → SQLite (`db/abi_state.db`)
* Default transports → In-memory EventBus and SSE streaming
* Fully interoperable with **AE SDK v0.3.6**
* Designed for modular extension to Kafka / GCP Pub/Sub

---

## Definition of Done (Phase 3E)

* [x] Keyring + Admission handshake validated
* [x] Policy enforcement functional
* [x] SSE endpoint (`/subscribe/{topic}`) verified via bus loopback
* [x] All tests passing (ABI + AE SDK)
* [ ] JWT grant + verified `/emit` endpoint (Phase 3F)

---

## Next Steps

**Phase 3F** — JWT-based emit verification and session token issuance
**Phase 4** — Kafka adapter and distributed event policy
**Phase 5** — ABI federation + UIX mesh orchestration

---

**Repository:** `github.com/invictus-insights/abi_service`
**Author:** Invictus Insights R&D
**Version:** 0.3.6 (Phase 3E All Green)
**License:** Proprietary / Pending Patent Filing
