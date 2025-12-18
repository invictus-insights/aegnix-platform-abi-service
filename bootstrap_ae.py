# scripts/bootstrap_ae.py
"""
Bootstrap a developer AE into the ABI keyring + policy.
Use this before pointing an external dev's AE at the cloud ABI.
"""

from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.policy import PolicyEngine
from aegnix_core.crypto import ed25519_generate
from aegnix_core.utils import b64e
from aegnix_core.storage import load_storage_provider

AE_ID = "sub_ae"
# DB_PATH = "db/abi_state.db"


def main():
    # Generate raw keypair
    priv_raw, pub_raw = ed25519_generate()

    # Correct Base64 versions
    priv_b64 = b64e(priv_raw)
    pub_b64 = b64e(pub_raw)

    print("\n=== AEGNIX AE Bootstrap ===")
    print(f"AE ID: {AE_ID}")

    # Add developer AE to the keyring
    # ring = ABIKeyring(db_path=DB_PATH)
    store = load_storage_provider()
    ring = ABIKeyring(store)

    rec = ring.add_key(
        ae_id=AE_ID,
        pubkey_b64=pub_b64,
        roles="producer",
        status="untrusted"
    )

    print(f"✓ Added key to keyring. Fingerprint: {rec.pub_key_fpr}")

    # Update policy granting publish rights
    p = PolicyEngine()
    p.allow(subject="fusion.topic", publisher=AE_ID)
    print("✓ Updated policy: allowed to publish fusion.topic")

    # Display developer keypair
    print("\n--- Developer keypair ---")
    print("Private (BASE64):", priv_b64)
    print("Public  (BASE64):", pub_b64)
    print("--------------------------\n")

    print("Deliver these Base64 keys to the developer. They can run AEClient immediately.")


if __name__ == "__main__":
    main()
