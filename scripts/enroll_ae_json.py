#!/usr/bin/env python3

import sys, os, json
from aegnix_core.crypto import ed25519_generate
from aegnix_core.utils import b64e
from aegnix_core.storage import SQLiteStorage, KeyRecord

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "db", "abi_state.db")

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "keys")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: python enroll_ae_json.py <ae_id1> <ae_id2> ...")
        sys.exit(1)

    store = SQLiteStorage(DB_PATH)

    for ae_id in sys.argv[1:]:
        ae_id = ae_id.strip()
        print(f"\n=== Enrolling AE: {ae_id} ===")

        # 1. Generate keys
        priv_raw, pub_raw = ed25519_generate()
        priv_b64 = b64e(priv_raw)
        pub_b64 = b64e(pub_raw)

        # 2. Upsert into keyring (status untrusted)
        rec = KeyRecord(
            ae_id=ae_id,
            pubkey_b64=pub_b64,
            roles="",
            status="untrusted",
            expires_at=None
        )
        store.upsert_key(rec)

        # 3. Write JSON bundle for the AE
        out_path = os.path.join(OUTPUT_DIR, f"{ae_id}_key.json")
        with open(out_path, "w") as f:
            json.dump({
                "ae_id": ae_id,
                "public_key": pub_b64,
                "private_key": priv_b64
            }, f, indent=2)

        print(f"[OK] Created JSON key bundle → {out_path}")

    print("\n=== All AEs Enrolled ===")
    print("Give each AE its JSON file. The private key stays inside that JSON.\n")


if __name__ == "__main__":
    main()

