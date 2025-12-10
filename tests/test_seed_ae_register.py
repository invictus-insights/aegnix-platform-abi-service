import requests
from aegnix_core.crypto import ed25519_sign, b64d, b64e
from aegnix_core.utils import b64e

ABI_URL = "https://sendmygear-abi-service-alpha-967267621633.us-central1.run.app"

# -----------------------------------------------------------
# 1) INSERT YOUR seed_ae KEYS HERE
# -----------------------------------------------------------
SEED_AE_ID = "seed_ae"

SEED_PRIV_B64 = "mWIblXkC8okg1X0pLqzAH6jBUTZOdFIbNdHKMxBdOyM="


# normalize private key → bytes
try:
    SEED_PRIV = b64d(SEED_PRIV_B64)
except Exception:
    SEED_PRIV = SEED_PRIV_B64.encode("utf-8")

# -----------------------------------------------------------
# 2) /register → get challenge
# -----------------------------------------------------------
print("➡ requesting challenge...")
r = requests.post(f"{ABI_URL}/register", json={"ae_id": SEED_AE_ID})
print("register:", r.status_code, r.text)

payload = r.json()
nonce = b64d(payload["nonce"])

# -----------------------------------------------------------
# 3) sign challenge
# -----------------------------------------------------------
sig = ed25519_sign(SEED_PRIV, nonce)
sig_b64 = b64e(sig)

# -----------------------------------------------------------
# 4) POST /verify
# -----------------------------------------------------------
print("➡ verifying...")
v = requests.post(
    f"{ABI_URL}/verify",
    json={"ae_id": SEED_AE_ID, "signed_nonce_b64": sig_b64},
)
print("verify:", v.status_code, v.text)

data = v.json()

if not data.get("verified"):
    print("❌ verification failed!")
    exit(1)

access = data["access_token"]
refresh = data["refresh_token"]

print("✔ verified!")
print("   access:", access[:30], "...")
print("   refresh:", refresh[:30], "...")

# -----------------------------------------------------------
# 5) Declare capabilities so ABI accepts publishes/subscribes
# -----------------------------------------------------------
print("➡ declaring capabilities...")
headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}

cap_body = {
    "publishes": ["seed.agent.request"],
    "subscribes": [],
    "meta": {}
}

c = requests.post(f"{ABI_URL}/ae/capabilities", json=cap_body, headers=headers)
print("capabilities:", c.status_code, c.text)

# -----------------------------------------------------------
# 6) Emit a test message
# -----------------------------------------------------------
print("➡ emitting test message...")

emit_body = {
    "subject": "seed.agent.request",
    "payload": {"hello": "world"},
}

e = requests.post(
    f"{ABI_URL}/emit",
    json={
        "subject": "seed.agent.request",
        "producer": SEED_AE_ID,
        "payload": {"hello": "world"},
    },
    headers={"Authorization": f"Bearer {access}"}
)
print("emit:", e.status_code, e.text)

print("\n🎉 DONE — check Cloud Run logs for the emit event!")
