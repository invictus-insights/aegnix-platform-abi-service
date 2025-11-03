"""
ABI Emit Endpoint
-----------------

This route handles incoming signed messages ("envelopes")
from registered Atomic Experts (AEs) wishing to publish data
into the AEGNIX mesh.

In essence, this process is structured like a multi-stage security checkpoint:
     - (schema validation): To enter, you must first have the correct form
     - (policy check): Then the correct security clearance
     - (trusted key check): then a verifiable ID badge
     - (signature verification): a signed manifest proving the contents are genuine
Failure at any stage results in immediate denial and documentation of the attempt

Each message is verified against:
    1. Policy rules (who can publish what)
    2. The ABI Keyring (is the AE trusted?)
    3. Cryptographic signature validity (ed25519)

If all checks pass, the message is audited, dispatched through the
appropriate transport channel, and an "accepted" response is returned.

Audit logs and service logs are written to:
    - logs/abi_audit.log
    - logs/abi_service.log

Raises:
    HTTPException(403): If publishing is blocked by policy or trust rules.
    HTTPException(400): If signature verification fails.
    HTTPException(500): For unexpected internal errors.
"""

from fastapi import APIRouter, Request, HTTPException
from aegnix_core.logger import get_logger
from aegnix_core.utils import now_ts
from aegnix_core.envelope import Envelope
from aegnix_core.crypto import ed25519_verify
from aegnix_abi.policy import PolicyEngine
from aegnix_abi.audit import AuditLogger
from aegnix_abi.keyring import ABIKeyring
from aegnix_ae.transport import transport_factory

import base64
from aegnix_core.utils import b64d

# ---------------------------------------------------------------------
# Module-level setup
# ---------------------------------------------------------------------

#: FastAPI router for the ABI emit service
router = APIRouter()

#: Central service logger (writes to logs/abi_service.log)
log = get_logger("ABI.Emit", to_file="logs/abi_service.log")

#: Policy engine used to evaluate producer/subject publishing rights
policy = PolicyEngine()

#: Audit logger that records all emit events for traceability
audit = AuditLogger(file_path="logs/abi_audit.log")

#: Persistent keyring storing AE public keys and trust states
keyring = ABIKeyring(db_path="db/abi_state.db")

# ---------------------------------------------------------------------
# Endpoint definition
# ---------------------------------------------------------------------

@router.post("/")
async def emit_message(req: Request):
    """
    Handle an incoming signed message ("envelope") emitted by an AE.

    This endpoint performs a full validation workflow:
        1. Parses the incoming JSON into an Envelope object.
        2. Checks the AE's publish permission using PolicyEngine.
        3. Confirms the AE's trust status via ABIKeyring.
        4. Verifies the envelope signature using ed25519.
        5. Audits and dispatches the validated envelope through
           the selected transport mechanism (e.g., Pub/Sub, local).

    Args:
        req (Request): The FastAPI request containing JSON payload.

    Returns:
        dict: Confirmation of accepted message:
              {"status": "accepted", "subject": "<subject>"}

    Raises:
        HTTPException(403): When policy or trust validation fails.
        HTTPException(400): When signature verification fails.
        HTTPException(500): On any other internal error.
    """
    try:
        # Parse the incoming JSON request body
        raw = await req.json()
        env = Envelope.from_dict(raw)  # raises if schema is invalid

        # 1) Policy check
        if not policy.can_publish(env.subject, env.producer):
            audit.log_event("emit_blocked_policy", {
                "producer": env.producer,
                "subject": env.subject
            })
            raise HTTPException(status_code=403, detail="Publish not allowed by policy")

        # 2) Trust check
        rec = keyring.get_key(env.producer) or keyring.get_key(env.key_id)
        if not rec or rec.status != "trusted":
            audit.log_event("emit_blocked_trust", {
                "producer": env.producer,
                "key_id": env.key_id
            })
            raise HTTPException(status_code=403, detail="AE not trusted")

        # 3) Signature verification
        try:
            pub_raw = base64.b64decode(rec.pubkey_b64)
            sig_raw = b64d(env.sig) if isinstance(env.sig, str) else env.sig
            ok = ed25519_verify(pub_raw,
                                sig_raw,
                                env.to_signing_bytes()
                                )
        except Exception as e:
            log.error({"event": "emit_sig_error", "error": str(e)})
            raise HTTPException(status_code=400, detail="Signature verification failed")

        # ok = ed25519_verify(
        #     pub_b64=rec.pubkey_b64,
        #     message=env.to_bytes(),
        #     sig=env.sig
        # )
        if not ok:
            audit.log_event("emit_blocked_sig", {
                "producer": env.producer,
                "subject": env.subject
            })
            raise HTTPException(status_code=400, detail="Invalid signature")

        # 4) Audit successful receipt
        audit.log_event("emit_received", {
            "ts": now_ts(),
            "producer": env.producer,
            "subject": env.subject,
            "labels": env.labels
        })

        # 5) Dispatch through the appropriate transport mechanism
        tx = transport_factory()
        tx.publish(env.subject, env.to_json())

        # 6) Log successful processing
        audit.log_event("emit_processed", {
            "producer": env.producer,
            "subject": env.subject,
            "transport": type(tx).__name__
        })

        return {"status": "accepted", "subject": env.subject}

    except HTTPException:
        # Re-raise known FastAPI exceptions without modification
        raise
    except Exception as e:
        # Log unexpected errors and raise as HTTP 500
        log.error({"event": "emit_error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
