from fastapi import APIRouter
from aegnix_abi.keyring import ABIKeyring


router = APIRouter()
keyring = ABIKeyring(db_path="db/abi_state.db")

@router.get("/keys")
def list_keys():
    """List all registered AEs and their key metadata."""
    return {"keys": keyring.list_keys()}

@router.post("/keys/add")
def add_key(ae_id: str, pubkey_b64: str):
    rec = keyring.add_key(ae_id, pubkey_b64)
    return {"status": "added", "record": rec.__dict__}

@router.post("/keys/revoke")
def revoke_key(ae_id: str):
    keyring.revoke_key(ae_id)
    return {"status": "revoked", "ae_id": ae_id}
