# tests/test_emit_verified.py

"""
Test Suite: Verified Emission (Phase 3F)
----------------------------------------

This suite validates end-to-end behavior of the /emit route with JWT,
policy, trust, and signature enforcement.

Covers:
    Valid token + trusted AE + valid sig  → 200 Accepted
    Missing Bearer                        → 401
    Bad token                             → 401
    Token / producer mismatch             → 403
    Policy deny                           → 403
    Bad signature                         → 400
"""

import hashlib
import pytest
from fastapi.testclient import TestClient
from fastapi import status

from main import app
from auth import issue_access_token
from aegnix_core.crypto import (
    ed25519_generate,
    ed25519_sign,
    compute_pubkey_fingerprint,   # NEW: for key_id
)
from aegnix_core.envelope import Envelope
from aegnix_core.utils import b64e
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.policy import PolicyEngine
import routes.emit as emit_route


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def setup_keyring(tmp_path_factory):
    """
    Create a temporary keyring and trusted AE entry.
    """
    tmp_db = tmp_path_factory.mktemp("abi") / "abi_state.db"
    keyring = ABIKeyring(db_path=str(tmp_db))

    # Generate AE keypair for tests
    priv, pub = ed25519_generate()
    pub_b64 = b64e(pub).decode()

    # Store as trusted in the keyring (ABI side)
    keyring.add_key("fusion_ae", pub_b64, status="trusted")

    # Point the live route's keyring at our temp DB-backed instance
    emit_route.keyring = keyring

    return keyring, priv, pub


@pytest.fixture(autouse=True)
def allow_policy():
    """
    Allow fusion_ae to publish fused.track subject for happy-path tests.
    """
    p = PolicyEngine()
    p.allow(subject="fused.track", publisher="fusion_ae")
    # Inject policy into the live emit route
    emit_route.policy = p
    return p


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def make_envelope(
    subject: str = "fused.track",
    producer: str = "fusion_ae",
    priv=None,
    pub=None,
    valid_sig: bool = True,
):
    """
    Build an Envelope that matches the current ABI emit contract:

      - Uses Envelope.make(...)
      - key_id = fingerprint(pubkey) when pub is given
      - Signature over env.to_signing_bytes()

    NOTE:
      This is a *service-side* test harness; we're impersonating an AE SDK.
    """
    # Compute key_id from pubkey fingerprint, if provided
    key_id = None
    if pub is not None:
        pub_b64 = b64e(pub).decode()
        key_id = compute_pubkey_fingerprint(pub_b64)

    env = Envelope.make(
        producer=producer,
        subject=subject,
        payload={"lat": 38.7, "lon": -104.7},
        labels=["CUI"],
        key_id=key_id or producer,  # fallback for older paths
    )

    data = env.to_signing_bytes()
    print("SIGN_HASH:", hashlib.sha256(data).hexdigest())

    # Good or bad signature depending on test
    if priv is not None and valid_sig:
        sig = ed25519_sign(priv, data)
    else:
        sig = b"bad_sig"

    env.sig = b64e(sig).decode()
    return env.to_dict()


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------

def test_valid_emit(client, setup_keyring):
    keyring, priv, pub = setup_keyring
    token = issue_access_token("fusion_ae", "session-1")

    env = make_envelope(priv=priv, pub=pub)

    res = client.post(
        "/emit",
        headers={"Authorization": f"Bearer {token}"},
        json=env,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    body = res.json()
    assert body["status"] == "accepted"


def test_missing_bearer(client):
    res = client.post("/emit", json={})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "bearer" in res.text.lower()


def test_bad_token(client):
    res = client.post(
        "/emit",
        headers={"Authorization": "Bearer not.a.valid.token"},
        json={},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_token_producer_mismatch(client, setup_keyring):
    keyring, priv, pub = setup_keyring
    # Token for another AE
    token = issue_access_token("rogue-ae", "session-x")

    # Envelope claims to be from fusion_ae
    env = make_envelope(priv=priv, pub=pub, producer="fusion_ae")

    res = client.post(
        "/emit",
        headers={"Authorization": f"Bearer {token}"},
        json=env,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "mismatch" in res.text.lower()


def test_policy_denied(client, setup_keyring):
    keyring, priv, pub = setup_keyring
    token = issue_access_token("fusion_ae", "session-2")

    # Disallowed subject
    env = make_envelope(subject="classified.data", priv=priv, pub=pub)

    res = client.post(
        "/emit",
        headers={"Authorization": f"Bearer {token}"},
        json=env,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "policy" in res.text.lower()


def test_invalid_signature(client, setup_keyring):
    keyring, priv, pub = setup_keyring
    token = issue_access_token("fusion_ae", "session-3")

    # Env has correct structure + key_id, but bad signature
    env = make_envelope(valid_sig=False, pub=pub)

    res = client.post(
        "/emit",
        headers={"Authorization": f"Bearer {token}"},
        json=env,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "signature" in res.text.lower()
