# tests/test_ae_register_real_and_emit_full.py
import pytest
import time

from aegnix_ae.client_v2 import AEClient
from aegnix_core.crypto import ed25519_generate, b64e
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.policy import PolicyEngine

ABI_URL = "http://localhost:8080"
DB_PATH = "db/abi_state.db"

# --------------------------------------------------------------------
# FIXTURE: Generate fresh AE keypair for the test
# --------------------------------------------------------------------
@pytest.fixture
def fusion_keypair():
    priv, pub = ed25519_generate()
    return {
        "priv": priv,
        "pub": pub,
        "pub_b64": b64e(pub),
    }

# --------------------------------------------------------------------
# FIXTURE: Bootstrap keyring + policy BEFORE the test AE registers
# --------------------------------------------------------------------
@pytest.fixture
def bootstrap_local_abi(fusion_keypair):
    """Preload ABI keyring + policy so register() succeeds."""
    ring = ABIKeyring(db_path=DB_PATH)

    # Add key with fingerprint auto-generated
    ring.add_key(
        ae_id="fusion_ae",
        pubkey_b64=fusion_keypair["pub_b64"],
        roles="producer",
        status="trusted"
    )

    # Policy: allow fusion_ae to publish fusion.topic
    p = PolicyEngine()
    p.allow(subject="fusion.topic", publisher="fusion_ae")

    return True

# --------------------------------------------------------------------
# E2E: Full test — real crypto, real challenge/verify, real emit()
# --------------------------------------------------------------------
def test_ae_register_real_and_emit_full(fusion_keypair, bootstrap_local_abi):
    """
    FULL E2E:
    1. ABI keyring bootstrap
    2. Real challenge→verify
    3. JWT session creation
    4. Real emit() to ABI
    """

    ae = AEClient(
        name="fusion_ae",
        abi_url=ABI_URL,
        keypair={
            "priv": fusion_keypair["priv"],
            "pub":  fusion_keypair["pub"],
        },
        publishes=["fusion.topic"],
        subscribes=[],
        transport="http",
    )

    # ---------------------------------------------------------------
    # Registration: challenge/verify + session issuance
    # ---------------------------------------------------------------
    assert ae.register_with_abi(), "AE must register successfully."

    # Assert session created
    assert ae.session is not None, "Session should exist after register()."
    assert ae.session.access_token is not None
    assert ae.session.refresh_token is not None

    # ---------------------------------------------------------------
    # Emit test message
    # ---------------------------------------------------------------
    ae.emit("fusion.topic", {"track_id": "E2E-FULL-PASS"})

    # Let ABI logs flush a moment (optional)
    time.sleep(0.2)

    # If no exception raised, emit() succeeded
    assert True
