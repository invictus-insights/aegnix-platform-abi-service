# test_emit_signature.py

from fastapi.testclient import TestClient
from main import app
import pytest
from aegnix_abi.keyring import ABIKeyring
from aegnix_core.envelope import Envelope
from aegnix_core.crypto import sign_envelope, ed25519_generate
from aegnix_core.utils import b64e, b64d
from aegnix_abi.policy import PolicyEngine

client = TestClient(app)


"""
Deprecated Test — Phase 3E
--------------------------
This test validated the open /emit/ endpoint before JWT enforcement.
Now skipped pending the full JWT + AdmissionService integration
planned for Phase 3F.

Once the new AE verification and token issuance flow is implemented,
this test will be replaced by:
    • test_emit_with_valid_jwt
    • test_emit_rejects_invalid_jwt
"""
@pytest.mark.skip(reason="JWT authorization flow pending — will be rewritten in Phase 3F")
def test_emit_requires_valid_signature(tmp_path, monkeypatch):
    """
    Test Suite: ABI Emit Endpoint
    -----------------------------

    This test validates the behavior of the `/emit/` FastAPI endpoint
    responsible for receiving and verifying signed messages ("envelopes")
    from Atomic Experts (AEs) within the AEGNIX framework.

    Focus:
        • Ensures valid envelopes with proper signatures are accepted.
        • Confirms policy and trust checks succeed under normal conditions.
        • Uses FastAPI's in-memory TestClient to simulate HTTP requests.

    Key components used in this test:
        - ABIKeyring: Stores and verifies trusted AE public keys.
        - PolicyEngine: Defines publishing rules for subjects and labels.
        - Envelope: Message container for signed payloads.
        - ed25519_generate / ed25519_sign: Crypto utilities for AE identity.

    Run this test with:
        pytest -v tests/test_emit_valid_signature.py
    """
    # Trust key
    kr = ABIKeyring("db/abi_state.db")
    priv, pub = ed25519_generate()
    pub_b64 = b64e(pub).decode()
    kr.add_key("fusion_ae", pub_b64)

    # Allow policy
    p = PolicyEngine()
    p.allow("fusion.topic", publisher="fusion_ae", labels=["default"])

    # Build envelope and sign
    env = Envelope.make(
        producer="fusion_ae",
        subject="fusion.topic",
        payload={"track_id":"ABC"},
        labels=["default"],
        key_id=pub_b64
    )
    # env.sig = ed25519_sign(env.to_bytes(), priv)
    env = sign_envelope(env, priv, pub_b64)

    r = client.post("/emit/", json=env.to_dict())
    assert r.status_code == 200, r.text
