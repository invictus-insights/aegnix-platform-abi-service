from fastapi import APIRouter, Body
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.policy import PolicyEngine


policy = PolicyEngine()
router = APIRouter()
keyring = ABIKeyring(db_path="db/abi_state.db")

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