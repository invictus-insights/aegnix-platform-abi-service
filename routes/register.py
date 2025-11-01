# abi_service/routes/register.py
from fastapi import APIRouter, Request
from aegnix_abi.admission import AdmissionService
from aegnix_abi.keyring import ABIKeyring
from aegnix_core.logger import get_logger

router = APIRouter()
log = get_logger("ABI.Register")

keyring = ABIKeyring()
admission = AdmissionService(keyring)

@router.post("/register")
async def issue_challenge(ae_id: str, request: Request):
    log.info({"route": "/register", "ae_id": ae_id})
    nonce = admission.issue_challenge(ae_id)
    log.info({"route": "/register", "status": "challenge_issued", "ae_id": ae_id, "nonce": nonce})
    return {"ae_id": ae_id, "nonce": nonce}

@router.post("/verify")
async def verify_response(ae_id: str, signed_nonce_b64: str, request: Request):
    ok, reason = admission.verify_response(ae_id, signed_nonce_b64)
    log.info({
        "route": "/verify",
        "ae_id": ae_id,
        "verified": ok,
        "reason": reason
    })
    return {"ae_id": ae_id, "verified": ok, "reason": reason}