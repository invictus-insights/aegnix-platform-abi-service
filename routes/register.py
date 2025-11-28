# abi_service/routes/register.py
import os, time, jwt
from fastapi import APIRouter, HTTPException, Body
from aegnix_abi.admission import AdmissionService
from aegnix_abi.keyring import ABIKeyring
from aegnix_core.logger import get_logger

from sessions import SessionManager

router = APIRouter()
log = get_logger("ABI.Register")
keyring = ABIKeyring(db_path="db/abi_state.db")
admission = AdmissionService(keyring)
session_manager: SessionManager = None

JWT_SECRET = os.getenv("ABI_JWT_SECRET", "change-me")
ACCESS_TTL = int(os.getenv("ABI_JWT_TTL_SECONDS", "300"))


@router.post("/register")
def issue_challenge(ae_id: str = Body(..., embed=True)):
    """Issue a cryptographic challenge (nonce) to AE."""
    try:
        nonce_b64 = admission.issue_challenge(ae_id)
        log.info({"event": "challenge_issued", "ae_id": ae_id})
        return {"ae_id": ae_id, "nonce": nonce_b64}
    except Exception as e:
        log.error({"event": "challenge_error", "ae_id": ae_id, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/verify")
def verify_response(ae_id: str = Body(...), signed_nonce_b64: str = Body(...)):
    """
    Verify AE’s signed challenge response, create a trust session,
    issue short-lived access JWT and long-lived refresh token.

    PHASE 4A OUTPUT:
    {
        "ae_id": "...",
        "verified": true,
        "session_id": "sid-uuid",
        "access_token": "<jwt>",
        "expires_in": 300,
        "refresh_token": "<opaque>",
        "refresh_expires_in": 86400
    }
    """

    if session_manager is None:
        raise RuntimeError("SessionManager not initialized in register route")

    try:
        # ------------------------------------------------------
        # 1. Check AE record
        # ------------------------------------------------------
        rec = keyring.get_key(ae_id)
        if not rec or rec.status == "revoked":
            log.warning(f"[VERIFY] AE '{ae_id}' not found or revoked")
            raise HTTPException(status_code=403, detail="AE not allowed")

        # ------------------------------------------------------
        # 2. Validate challenge signature
        # ------------------------------------------------------
        ok, reason = admission.verify_response(ae_id, signed_nonce_b64)
        log.info({"event": "verify_result", "ae_id": ae_id, "verified": ok})
        if not ok:
            return {"ae_id": ae_id, "verified": False, "reason": reason}

        # ------------------------------------------------------
        # 3. Determine AE roles (for JWT claims)
        # ------------------------------------------------------
        roles = getattr(rec, "roles", "") or "producer"

        # ------------------------------------------------------
        # 4. Create Session (Phase 4A)
        # ------------------------------------------------------
        pubkey_fpr = rec.pub_key_fpr  # fingerprint from ABIKeyring

        session = session_manager.create_session(
            subject=ae_id,
            pubkey_fpr=pubkey_fpr,
            profile="tactical_ae",
            metadata={"roles": roles}
        )

        # ------------------------------------------------------
        # 5. Create Refresh Token (Phase 4A)
        # ------------------------------------------------------
        raw_refresh, refresh_rec = session_manager.create_refresh_token(
            session_id=session.id,
            profile="tactical_ae"
        )

        # ------------------------------------------------------
        # 6. Generate Access JWT (short-lived)
        # ------------------------------------------------------
        now = int(time.time())
        access_token = jwt.encode(
            {
                "sub": ae_id,
                "sid": session.id,              # NEW — session binding
                "roles": roles,
                "iat": now,
                "exp": now + ACCESS_TTL
            },
            JWT_SECRET,
            algorithm="HS256"
        )

        # ------------------------------------------------------
        # 7. Respond to AE with grant + refresh
        # ------------------------------------------------------
        log.info(f"[VERIFY] AE '{ae_id}' verified — session + JWT issued")

        return {
            "ae_id": ae_id,
            "verified": True,
            "session_id": session.id,
            "access_token": access_token,
            "expires_in": ACCESS_TTL,
            "refresh_token": raw_refresh,                     # opaque, raw
            "refresh_expires_in": refresh_rec.expires_at - refresh_rec.created_at,
            "reason": "verified"
        }

    except HTTPException:
        raise

    except Exception as e:
        log.error({"event": "verify_error", "ae_id": ae_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# @router.post("/verify")
# def verify_response(ae_id: str = Body(...), signed_nonce_b64: str = Body(...)):
#     """
#     Verify AE’s signed response to challenge and issue a session grant.
#
#     1. Confirm AE exists (and is not revoked) in keyring.
#     2. Validate signature against stored nonce via AdmissionService.
#     3. Issue a short-lived JWT grant if verified.
#
#     Roles:
#         - Read from keyring.rec.roles if present.
#         - Default to "producer" if empty.
#         - Roles are metadata for now; policy remains the true gatekeeper.
#     """
#     try:
#         # Retrieve AE key record
#         rec = keyring.get_key(ae_id)
#         if not rec or rec.status == "revoked":
#             log.warning(f"[VERIFY] AE '{ae_id}' not found or revoked")
#             raise HTTPException(status_code=403, detail="AE not allowed")
#         # if not rec or rec.status != "trusted":
#         #     log.warning(f"[VERIFY] AE '{ae_id}' not trusted or not found")
#         #     raise HTTPException(status_code=403, detail="AE not trusted")
#
#         # Validate signature through AdmissionService
#         ok, reason = admission.verify_response(ae_id, signed_nonce_b64)
#         log.info({"event": "verify_result", "ae_id": ae_id, "verified": ok})
#         if not ok:
#             return {"ae_id": ae_id, "verified": False, "reason": reason}
#
#         # Roles from keyring
#         roles = getattr(rec, "roles", "") or "producer"
#
#         # Issue short-lived JWT session token
#         now = int(time.time())
#         token = jwt.encode(
#             {"sub": ae_id, "roles": roles, "iat": now, "exp": now + JWT_TTL},
#             JWT_SECRET,
#             algorithm="HS256"
#         )
#
#         log.info(f"[VERIFY] AE '{ae_id}' verified successfully — JWT issued")
#
#         return {"ae_id": ae_id, "verified": True, "reason": "verified", "grant": token}
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         log.error({"event": "verify_error", "ae_id": ae_id, "error": str(e)})
#         raise HTTPException(status_code=500, detail=str(e))
