"""
ABI Emit Endpoint (Phase 3F)
----------------------------

This route handles authenticated, signed messages ("envelopes")
from registered Atomic Experts (AEs) wishing to publish data
into the AEGNIX mesh.

Each emit request now enforces **session-verified, policy-checked,
and signature-validated emission**, completing the 3F security layer.

Security Flow
----------------------------
1. **JWT Authentication**
      - Requires a valid Bearer token (issued at AE registration)
      - Token must include a valid `sub` (AE ID) and `sid` (session ID)
2. **Schema Validation**
      - Incoming payload must form a valid Envelope
3. **Policy Enforcement**
      - ABI verifies the AE is permitted to publish on the given subject
4. **Trust Verification**
      - Producer’s public key must exist and be marked as “trusted”
5. **Signature Verification**
      - ed25519 signature checked against envelope bytes
6. **Audit Trail**
      - Every event (allowed or denied) recorded with AE ID, session ID,
        subject, reason, and timestamp

If all checks pass, the envelope is dispatched through the transport
layer and locally fanned out through the event bus.

Audit logs and service logs are written to:
    • logs/abi_audit.log
    • logs/abi_service.log

Raises:
    HTTPException(401): If the JWT token is missing, expired, or invalid.
    HTTPException(403): If publishing is blocked by policy or trust rules.
    HTTPException(400): If signature verification fails.
    HTTPException(500): For unexpected internal errors.
"""

import hashlib
from fastapi import APIRouter, Request, HTTPException, Header, Depends
from typing import Optional, cast
from aegnix_core.logger import get_logger
from aegnix_core.utils import now_ts, b64d
from aegnix_core.envelope import Envelope
from aegnix_core.crypto import ed25519_verify
from aegnix_core.transport import transport_factory
from aegnix_abi.policy import PolicyEngine
from aegnix_abi.audit import AuditLogger
from aegnix_abi.keyring import ABIKeyring

from bus import bus
from auth import verify_token
# from runtime_registry import RuntimeRegistry
from abi_state import ABIState




# injected by main.py
# runtime_registry: RuntimeRegistry = cast(RuntimeRegistry, None)
abi_state: ABIState = cast(ABIState, None)
session_manager = None

log = get_logger("ABI.Emit", to_file="logs/abi_service.log")
log.info({
    "event": "emit_route_initialized",
    "heartbeat_provider": "ABIState",
})


# ---------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------


router = APIRouter()  # FastAPI router for the ABI emit service

log = get_logger("ABI.Emit", to_file="logs/abi_service.log")  # Central logger
policy = PolicyEngine()                                       # Policy engine
audit = AuditLogger(file_path="logs/abi_audit.log")           # Audit logger
keyring: Optional[ABIKeyring] = None

# Standardized audit event labels
EVENT_POLICY_DENY = "emit_blocked_policy"
EVENT_SIG_FAIL = "emit_blocked_sig"
EVENT_TRUST_FAIL = "emit_blocked_trust"
EVENT_ACCEPTED = "emit_processed"
EVENT_RECEIVED = "emit_received"


# ---------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------
@router.post("")
@router.post("/")
async def emit_message(req: Request, authorization: str | None = Header(default=None)):
#async def emit_message(req: Request, authorization: str | None = Header(default=None)):
    """
    Validate, authenticate, and dispatch a signed envelope from an AE.

    Performs full security verification:
    - JWT token authentication (session-scoped)
    - Policy, trust, and signature validation
    - Per-AE session logging for traceability
    """
    try:
        # --- JWT Authentication -------------------------------------
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")

        token = authorization.split(" ", 1)[1]

        try:
            claims = verify_token(token)
            ae_id = claims.get("sub")
            roles = claims.get("roles", "")

            log.info({
                "event": "jwt_ok",
                "sub": ae_id,
                "roles": roles,
            })

        except HTTPException as e:
            log.error({
                "event": "jwt_invalid",
                "detail": e.detail,
                # Just a prefix
                "token_prefix": token[:32],
            })
            raise  # propagate token expired / invalid
        except Exception as e:
            log.exception({"event": "jwt_decode_error"})
            raise HTTPException(status_code=401, detail="Invalid token")

        # --- Parse & rebuild envelope --------------------------------
        raw = await req.json()
        env = Envelope.from_dict(raw)

        # Ensure token subject (sub) matches envelope producer
        if env.producer != ae_id:
            raise HTTPException(status_code=403, detail="Producer mismatch with token")

        # --- Trust Verification -------------------------------------
        if keyring is None:
            raise HTTPException(status_code=500, detail="Keyring not initialized")

        rec = keyring.get_by_aeid(env.producer)

        # If envelope declares key version/fingerprint
        if not rec and env.key_id:
            rec = keyring.get_by_fpr(env.key_id)

        if not rec:
            log.error({"event": "trust_debug", "msg": "AE key not found", "ae_id": env.producer})
            raise HTTPException(status_code=403, detail="AE not found in keyring")


        # --- DEBUG: verify which key is loaded ---
        log.info({
            "event": "trust_debug",
            "ae_id": env.producer,
            "db_path": getattr(keyring, "db_path", "?"),
            "pubkey_b64_prefix": rec.pubkey_b64[:16],
            "rec_status": rec.status
        })

        if rec.status != "trusted":
            audit.log_event(EVENT_TRUST_FAIL, {
                "producer": env.producer,
                "key_id": env.key_id
            })
            raise HTTPException(status_code=403, detail="AE not trusted")

        # --- Policy Enforcement (Step 3.3) ---------------------------
        effective_roles = (rec.roles or roles)

        if not policy.can_publish(env.producer, env.subject, roles=effective_roles):
            audit.log_event(EVENT_POLICY_DENY, {
                "producer": env.producer,
                "subject": env.subject,
                "reason": "policy_denied",
                "roles": roles,
            })
            raise HTTPException(status_code=403, detail="Publish not allowed by policy")

        # --- Signature Verification ---------------------------------
        pub_raw = b64d(rec.pubkey_b64)
        sig_raw = b64d(env.sig) if isinstance(env.sig, str) else env.sig

        log.info({
            "event": "sig_debug",
            "to_sign_bytes_len": len(env.to_signing_bytes()),
            "sig_len": len(sig_raw),
            "first_bytes": env.to_signing_bytes()[:50].hex()
        })

        log.info({
            "event": "sig_hash_debug",
            "hash": hashlib.sha256(env.to_signing_bytes()).hexdigest()
        })

        ok = ed25519_verify(pub_raw, sig_raw, env.to_signing_bytes())
        if not ok:
            audit.log_event(EVENT_SIG_FAIL , {
                "producer": env.producer, "subject": env.subject
            })
            raise HTTPException(status_code=400, detail="Invalid signature")

        # --- Audit & Dispatch -----------------------------------------
        # include per-AE session ID from JWT for traceability
        session_id = claims.get("sid")

        # --- Phase 4B Step-2: Semantic heartbeat -----------------------
        if abi_state is None:
            log.error({
                "event": "heartbeat_missing",
                "ae_id": ae_id,
                "session_id": session_id,
                "reason": "abi_state_not_injected"
            })
        else:
            abi_state.heartbeat(
                ae_id=ae_id,
                session_id=session_id,
                source="emit"
            )

        # # --- NEW: runtime registry touch (AE is alive)
        # if runtime_registry is None:  # type: ignore[truthy-function]
        #     log.error({
        #         "event": "runtime_touch_missing",
        #         "ae_id": ae_id,
        #         "session_id": session_id,
        #         "reason": "runtime_registry_is_none"
        #     })
        # else:
        #     runtime_registry.touch(ae_id, session_id=session_id)
        #     log.info({
        #         "event": "runtime_touch",
        #         "ae_id": ae_id,
        #         "session_id": session_id,
        #     })

        audit.log_event(EVENT_RECEIVED, {
            "ts": now_ts(), "producer": env.producer,
            "session_id": session_id, "subject": env.subject,
            "labels": env.labels
        })

        tx = transport_factory()
        tx.publish(env.subject, env.to_json())

        log.info({
            "event": "sig_debug",
            "sig_len": len(env.sig or ""),
            "subject": env.subject,
            "to_sign_bytes_len": len(env.to_signing_bytes()),
            "first_bytes": env.to_signing_bytes()[:32].hex()
        })

        audit.log_event(EVENT_ACCEPTED, {
            "producer": env.producer,
            "subject": env.subject,
            "transport": type(tx).__name__
        })

        # --- Local fan-out via SSE bus -------------------------------
        await bus.publish(env.subject, raw)

        return {"status": "accepted", "subject": env.subject, "ts": now_ts()}

    except HTTPException:
        raise
    except Exception as e:
        log.error({"event": "emit_error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
