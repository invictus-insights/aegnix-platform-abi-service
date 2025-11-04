# abi_service/routes/register.py
import os, time, jwt
from fastapi import APIRouter, HTTPException, Body
from aegnix_abi.admission import AdmissionService
from aegnix_abi.keyring import ABIKeyring
from aegnix_core.logger import get_logger

router = APIRouter()
log = get_logger("ABI.Register")
keyring = ABIKeyring(db_path="db/abi_state.db")
admission = AdmissionService(keyring)

JWT_SECRET = os.getenv("ABI_JWT_SECRET", "dev-secret-change-me")
JWT_TTL = int(os.getenv("ABI_JWT_TTL_SECONDS", "600"))


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
    Verify AE’s signed response to challenge and issue a session grant.

    1. Confirm AE exists and is trusted in keyring.
    2. Validate signature against stored nonce via AdmissionService.
    3. Issue a short-lived JWT grant if verified.
    """
    try:
        # Retrieve AE key record
        rec = keyring.get_key(ae_id)
        if not rec or rec.status != "trusted":
            log.warning(f"[VERIFY] AE '{ae_id}' not trusted or not found")
            raise HTTPException(status_code=403, detail="AE not trusted")

        # Validate signature through AdmissionService
        ok, reason = admission.verify_response(ae_id, signed_nonce_b64)
        log.info({"event": "verify_result", "ae_id": ae_id, "verified": ok})
        if not ok:
            return {"ae_id": ae_id, "verified": False, "reason": reason}

        # Prepare role(s)
        roles = getattr(rec, "roles", "") or "publisher"

        # Issue short-lived JWT session token
        now = int(time.time())
        token = jwt.encode(
            {"sub": ae_id, "roles": roles, "iat": now, "exp": now + JWT_TTL},
            JWT_SECRET,
            algorithm="HS256"
        )

        log.info(f"[VERIFY] AE '{ae_id}' verified successfully — JWT issued")

        return {"ae_id": ae_id, "verified": True, "reason": "verified", "grant": token}

    except HTTPException:
        raise
    except Exception as e:
        log.error({"event": "verify_error", "ae_id": ae_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

# @router.post("/verify")
# def verify_response(ae_id: str = Body(...), signed_nonce_b64: str = Body(...)):
#     ok, reason = admission.verify_response(ae_id, signed_nonce_b64)
#     log.info({"event":"verify_result","ae_id":ae_id,"verified":ok})
#     if not ok:
#         return {"ae_id": ae_id, "verified": False, "reason": reason}
#
#     # roles from keyring (string; optional)
#     rec = keyring.get_key(ae_id)
#     roles = getattr(rec, "roles", "") if rec else ""
#
#     now = int(time.time())
#     token = jwt.encode(
#         {"sub": ae_id, "roles": roles, "iat": now, "exp": now + JWT_TTL},
#         JWT_SECRET,
#         algorithm="HS256"
#     )
#     return {"ae_id": ae_id, "verified": True, "reason": "verified", "grant": token}
