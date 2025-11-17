# AEGNIX ABI Service

The **AEGNIX Agent Bridge Interface (ABI) Service** is the authenticated, trusted, cryptographically enforced coordination layer for the **AEGNIX Swarm Framework**.

It performs **admission**, **verification**, **policy enforcement**, **key trust management**, **event dispatch**, and **developer‑facing observability**, forming the backbone of secure multi‑agent operations across the swarm.

This service ensures that every Atomic Expert (AE):

* is **verified** (ed25519 dual‑crypto handshake)
* is **authenticated** (JWT session)
* is **authorized** (static + dynamic policy)
* is **trusted** (keyring‑managed public keys)
* is **audited** (non‑repudiation logs)
* is **coordinated** (EventBus + SSE routing for developers)

---

## Core Responsibilities

### 1. Admission (ed25519 Challenge‑Response)

The ABI issues a nonce, the AE signs it with its ed25519 private key, the ABI verifies the signature, then sets the AE to **trusted** and returns a **JWT session token**.

**Flow:**

```text
/register  →  nonce issued
/verify    →  signature checked, AE trusted, JWT granted
```

---

### 2. Verified Message Emission (`POST /emit`)

Each incoming message must:

1. Include a valid session JWT (`Bearer <token>`)
2. Declare a producer that matches JWT `sub`
3. Carry a proper Envelope (canonical AEGNIX format)
4. Pass policy checks (`can_publish`)
5. Match a **trusted** keyring entry
6. Have a valid Ed25519 signature over `to_signing_bytes()`

If all checks pass, the event is:

* published to the transport (local default)
* logged to audit
* fanned out through the EventBus
* reflected to any `/subscribe/<topic>` SSE clients

---

### 3. Policy Enforcement (Static + Dynamic)

The ABI merges:

* **Static `policy.yaml`**
* **Dynamic AE capabilities** from the SQLite capability table

This forms the **Effective Policy**, used for:

* `can_publish(ae_id, subject, roles)`
* `can_subscribe(ae_id, subject, roles)`

A background watcher hot‑reloads policy whenever YAML or capability rows change.

---

### 4. Keyring & Trust State

The keyring is stored in `db/abi_state.db` and provides:

* AE public key records
* roles (Phase 3G key‑authorized role merge)
* trust status (`trusted`, `untrusted`, `revoked`)
* expiration metadata
* audit logging on all key changes

Roles stored here override JWT roles for security reasons.

---

### 5. Developer Observability (`GET /subscribe/<topic>`, SSE)

The ABI includes a secure **Server‑Sent Events** endpoint for real‑time monitoring.

Security for SSE:

* JWT required
* keyring trust required
* policy controls subscription permissions

The EventBus bridges `publish(topic, message)` to active SSE streams.

---

## 📁 Directory Structure

```
abi_service/
├── main.py
├── bus.py
├── config/
│   └── policy.yaml
├── db/
│   └── abi_state.db
├── logs/
│   ├── abi_service.log
│   └── abi_audit.log
├── routes/
│   ├── admin.py
│   ├── audit.py
│   ├── capabilities.py
│   ├── emit.py
│   ├── register.py
│   └── subscribe.py
└── tests/
    ├── test_emit_verified.py
    ├── test_register_flow.py
    ├── test_policy_dynamic_merge.py
    └── test_subscribe_loopback.py
```

---

## Routes Overview

### `POST /register`

Begin admission, receive nonce.

### `POST /verify`

Submit signed nonce → trust elevation + JWT.

### `POST /emit`

Verified message emission.

### `POST /capabilities`

AE declares its publishes/subscribes (Phase 3G).

### `GET /subscribe/<topic>`

SSE stream for developers (policy controlled).

### `/admin/*`

Keyring management utilities.

### `/audit/*`

Audit records (JSONL entries).

---

## Policy Model

### Static Policy (`config/policy.yaml`)

Defines baseline swarm rules:

```yaml
subjects:
  fused.track:
    pubs: [fusion_ae]
    subs: [advisory_ae, roe_ae]
    labels: [CUI]

  fusion.topic:
    subs: [test_sse_ae]

roles:
  subscriber: {}
```

### Dynamic Capabilities

AEs may declare:

```json
{
  "publishes": ["fusion.topic"],
  "subscribes": ["roe.result"],
  "meta": {}
}
```

Stored in SQLite and merged automatically.

### Effective Policy

At runtime, the ABI enforces:

* **union** of static + dynamic rules
* keyring roles > JWT roles
* deny‑by‑default for unknown subjects

---

## Testing

Run full suite:

```bash
pytest -v -s --log-cli-level=DEBUG
```

Coverage includes:

* Verified signature checks
* JWT validation
* Role merge
* Policy merge
* SSE loopback
* Dynamic capability ingestion
* Full admission flow

All current tests: **PASSING**.

---

## Environment Variables

Set JWT secret:

```bash
export ABI_JWT_SECRET="mydevsecret123"
```

Files created automatically:

```
db/abi_state.db
logs/abi_service.log
logs/abi_audit.log
```

---

## 🗺 Roadmap (Phase 3 → 4)

### ✔ Phase 3F (Complete)

* Verified /emit
* JWT session enforcement
* Signature validation
* Trust‑state enforcement
* Static policy merging
* Developer SSE routing

### ✔ Phase 3G (Complete)

* Dynamic capability ingestion
* Effective Policy merge
* Role merge (keyring > JWT)
* Unknown‑subject protection

### ⬜ Phase 4A (Next)

* Remove backward‑compat shims
* Harden role system
* JWT refresh tokens
* AE revocation cascades

### ⬜ Phase 5

* Federated ABIs
* Cross‑domain trust
* Reflection Layer integration
* Purpose Policy (SPP) enforcement

---

## Version

**ABI Service:** v0.3.8 (Phase 3F/3G)
**License:** Proprietary – Patent filings pending
**Authors:** Invictus Insights R&D
