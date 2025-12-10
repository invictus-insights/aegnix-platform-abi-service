#!/usr/bin/env python3

import sys, os
from aegnix_core.crypto import ed25519_generate
from aegnix_core.utils import b64e
from aegnix_core.storage import SQLiteStorage, KeyRecord

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)   # parent of scripts/
DB_PATH = os.path.join(PROJECT_ROOT, "db", "abi_state.db")

def main():
    if len(sys.argv) != 2:
        print("Usage: python enroll_ae.py <ae_id>")
        sys.exit(1)

    ae_id = sys.argv[1].strip()
    print(f"\n=== Enrolling AE: {ae_id} ===")

    # 1. Generate keys
    priv_raw, pub_raw = ed25519_generate()
    priv_b64 = b64e(priv_raw)
    pub_b64 = b64e(pub_raw)

    print(f"[1] Generated new keypair")
    print(f"    Public Key (b64):  {pub_b64}")
    print(f"    Private Key (b64): {priv_b64}")

    # 2. Open storage
    store = SQLiteStorage(DB_PATH)

    # 3. Upsert key into keyring
    rec = KeyRecord(
        ae_id=ae_id,
        pubkey_b64=pub_b64,
        roles="",
        status="untrusted",
        expires_at=None
    )
    store.upsert_key(rec)
    print(f"[2] Keyring upsert complete")

    # 4. Verify insert by reading it back
    fetched = store.get_key(ae_id)
    if fetched is None:
        print(f"[ERROR] Keyring read-back FAILED. No record for AE: {ae_id}\n")
        sys.exit(1)

    print(f"[3] Keyring read-back:")
    print(f"    ae_id:       {fetched.ae_id}")
    print(f"    pubkey_b64:  {fetched.pubkey_b64}")
    print(f"    roles:       {fetched.roles}")
    print(f"    status:      {fetched.status}")
    print(f"    expires_at:  {fetched.expires_at}")

    print("\n=== SUCCESS ===")
    print("Store the PRIVATE key safely — your AE will need it to sign the registration challenge.\n")



if __name__ == "__main__":
    main()
