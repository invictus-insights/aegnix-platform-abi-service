from fastapi import APIRouter, Body, HTTPException, Header
import os
from aegnix_core.utils import now_ts
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.policy import PolicyEngine



policy = PolicyEngine()
router = APIRouter()
keyring = ABIKeyring(db_path="db/abi_state.db")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "supersecretadminkey123")

@router.get("/keys")
def list_keys():
    """List all registered AEs and their key metadata."""
    return {"keys": keyring.list_keys()}


@router.post("/keys/add")
def add_key(
    ae_id: str = Body(..., description="AE identifier"),
    pubkey_b64: str = Body(..., description="Base64 public key")
):
    """Provision a new AE public key into the ABI keyring."""
    rec = keyring.add_key(ae_id, pubkey_b64)
    return {"status": "added", "record": rec.__dict__}


@router.delete("/keys/{ae_id}")
def delete_key(ae_id: str, x_admin_token: str = Header(...)):
    """
    Delete an AE key. Requires admin authorization.
    """
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Unauthorized admin access")

    rec = keyring.get_key(ae_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Key not found")

    keyring.revoke_key(ae_id)
    keyring.store.log_event("key_deleted", {"ae_id": ae_id, "ts": now_ts()})
    return {"status": "deleted", "ae_id": ae_id}


# @router.post("/keys/trust")
# def trust_key(ae_id: str = Body(...)):
#     rec = keyring.get_key(ae_id)
#     if not rec:
#         raise HTTPException(status_code=404, detail="Key not found")
#     rec.status = "trusted"
#     keyring.store.upsert_key(rec)
#     keyring.store.log_event("key_trusted", {"ae_id": ae_id, "ts": now_ts()})
#     return {"status": "trusted", "ae_id": ae_id}
#


@router.post("/keys/revoke")
def revoke_key(ae_id: str = Body(...)):
    """Revoke a key from the ABI keyring."""
    keyring.revoke_key(ae_id)
    return {"status": "revoked", "ae_id": ae_id}


@router.get("/policy")
def list_policy():
    return {"rules": policy.rules}


@router.post("/policy/allow")
def policy_allow(subject: str = Body(...), publisher: str | None = Body(default=None),
                 subscriber: str | None = Body(default=None), labels: list[str] | None = Body(default=None)):
    policy.allow(subject, publisher=publisher, subscriber=subscriber, labels=labels or [])
    return {"status": "ok"}


@router.post("/policy/revoke")
def policy_revoke(subject: str = Body(...), publisher: str | None = Body(default=None),
                  subscriber: str | None = Body(default=None)):
    policy.revoke(subject, publisher=publisher, subscriber=subscriber)
    return {"status": "ok"}