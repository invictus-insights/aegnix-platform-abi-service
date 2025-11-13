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

import base64, hashlib, pytest, httpx
from fastapi.testclient import TestClient
from fastapi import status

from main import app
from auth import issue_token
from aegnix_core.crypto import ed25519_generate, ed25519_sign
from aegnix_core.envelope import Envelope
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.policy import PolicyEngine
import routes.emit as emit_route

# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8080"


# @pytest.fixture(scope="module")
# def client():
#     with httpx.Client(base_url=BASE_URL) as c:
#         yield c

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
    priv, pub = ed25519_generate()
    pub_b64 = base64.b64encode(pub).decode()
    keyring.add_key("fusion_ae", pub_b64, status="trusted")

    # Point the live route's keyring at our temp DB
    emit_route.keyring = keyring

    return keyring, priv, pub

@pytest.fixture(autouse=True)
def allow_policy():
    from routes import emit as emit_route
    p = PolicyEngine()
    p.allow(subject="fused.track", publisher="fusion_ae")
    emit_route.policy = p  # inject directly into the live route
    return p


# @pytest.fixture(autouse=True)
# def allow_policy():
#     """
#     Allow fusion_ae to publish fused.track subject for happy-path test.
#     """
#     p = PolicyEngine()
#     p.allow(subject="fused.track", publisher="fusion_ae")
#     return p

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def make_envelope(subject="fused.track", producer="fusion_ae", priv=None, valid_sig=True):
    env = Envelope(
        producer=producer,
        subject=subject,
        payload={"lat": 38.7, "lon": -104.7},
        labels=["CUI"]
    )
    data = env.to_signing_bytes()
    print("SIGN_HASH:", hashlib.sha256(data).hexdigest())

    if priv and valid_sig:
        sig = ed25519_sign(priv, data)
    else:
        sig = b"bad_sig"
    env.sig = base64.b64encode(sig).decode()
    env.key_id = producer
    return env.to_dict()

# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------

def test_valid_emit(client, setup_keyring):
    keyring, priv, _ = setup_keyring
    token = issue_token("fusion_ae", "session-1")
    env = make_envelope(priv=priv)

    res = client.post(
        "/emit",
        headers={"Authorization": f"Bearer {token}"},
        json=env,
    )
    assert res.status_code == status.HTTP_200_OK
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
    keyring, priv, _ = setup_keyring
    # Token for another AE
    token = issue_token("rogue-ae", "session-x")
    env = make_envelope(priv=priv, producer="fusion_ae")

    res = client.post(
        "/emit",
        headers={"Authorization": f"Bearer {token}"},
        json=env,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "mismatch" in res.text.lower()

def test_policy_denied(client, setup_keyring):
    keyring, priv, _ = setup_keyring
    token = issue_token("fusion_ae", "session-2")
    # Disallowed subject
    env = make_envelope(subject="classified.data", priv=priv)

    res = client.post(
        "/emit",
        headers={"Authorization": f"Bearer {token}"},
        json=env,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "policy" in res.text.lower()

def test_invalid_signature(client, setup_keyring):
    keyring, _, _ = setup_keyring
    token = issue_token("fusion_ae", "session-3")
    env = make_envelope(valid_sig=False)

    res = client.post(
        "/emit",
        headers={"Authorization": f"Bearer {token}"},
        json=env,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "signature" in res.text.lower()
