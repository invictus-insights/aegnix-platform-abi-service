# abi_service/routes/register.py
# from fastapi import APIRouter, Request
from fastapi import APIRouter, HTTPException, Body
from aegnix_abi.admission import AdmissionService
from aegnix_abi.keyring import ABIKeyring
from aegnix_core.logger import get_logger

router = APIRouter()
log = get_logger("ABI.Register")

keyring = ABIKeyring(db_path="db/abi_state.db")
admission = AdmissionService(keyring)

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
    """Verify AE’s signed response to challenge."""
    try:
        ok, reason = admission.verify_response(ae_id, signed_nonce_b64)
        log.info({"event": "verify_result", "ae_id": ae_id, "verified": ok})
        return {"ae_id": ae_id, "verified": ok, "reason": reason}
    except Exception as e:
        log.error({"event": "verify_error", "ae_id": ae_id, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

# keyring = ABIKeyring()
# admission = AdmissionService(keyring)
#
# @router.post("/register")
# async def issue_challenge(ae_id: str, request: Request):
#     log.info({"route": "/register", "ae_id": ae_id})
#     nonce = admission.issue_challenge(ae_id)
#     log.info({"route": "/register", "status": "challenge_issued", "ae_id": ae_id, "nonce": nonce})
#     return {"ae_id": ae_id, "nonce": nonce}
#
# @router.post("/verify")
# async def verify_response(ae_id: str, signed_nonce_b64: str, request: Request):
#     ok, reason = admission.verify_response(ae_id, signed_nonce_b64)
#     log.info({
#         "route": "/verify",
#         "ae_id": ae_id,
#         "verified": ok,
#         "reason": reason
#     })
#     return {"ae_id": ae_id, "verified": ok, "reason": reason}