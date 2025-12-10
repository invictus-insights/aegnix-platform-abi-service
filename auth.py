# abi_service/auth.py
"""
ABI Authentication Utilities
--------------------------------------
This module provides the core JWT helpers for all session-based
authentication inside the ABI Service.

It acts as the *single source of truth* for:
  • Access token issuance
  • Token verification
  • Common TTL / algorithm configuration

The ABI Service uses *access tokens* (short-lived JWTs) for:
  - /emit
  - /subscribe
  - /audit
  - /capabilities
  - /session/heartbeat
  - /session/refresh

Refresh tokens are **NOT JWTs** — they are opaque values stored
and validated by SessionManager. This module only handles access JWTs.
"""
import os, jwt, time
from fastapi import HTTPException

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
JWT_SECRET = os.getenv("ABI_JWT_SECRET", "change-me")
JWT_ALGO = os.getenv("ABI_JWT_ALGO", "HS256")

# Access token TTL (seconds)
ACCESS_TTL = int(os.getenv("ABI_JWT_TTL_SECONDS", "300"))  # default: 5 minutes

# print("ABI_JWT_SECRET at startup =", JWT_SECRET)


# ----------------------------------------------------------------------
# Issue Access Token
# ----------------------------------------------------------------------
def issue_access_token(ae_id: str, session_id: str, roles: str = "producer"):
    """
    Issue a short-lived access JWT bound to a specific AE + session.

    Claims:
      sub  -> AE identifier
      sid  -> session UUID
      roles -> roles declared at verify-time (string)
      iat  -> issuance time (UTC)
      exp  -> expiration time (UTC)

    Returns:
        str: Encoded JWT string
    """
    now = int(time.time())

    payload = {
        "sub": ae_id,
        "sid": session_id,
        "roles": roles,
        "iat": now,
        "exp": now + ACCESS_TTL,
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


# ----------------------------------------------------------------------
# Verify Access Token
# ----------------------------------------------------------------------
def verify_token(token: str):
    """
    Decode and validate an access JWT.

    Raises:
        HTTPException(401) if token is expired or invalid.

    Returns:
        dict: decoded JWT claims
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ----------------------------------------------------------------------
# TTL Check
# ----------------------------------------------------------------------
def get_token_expiration(token: str) -> int:
    """
    Utility for debugging / introspection:

    Returns:
        exp (unix timestamp)

    Raises:
        HTTPException if token invalid.
    """
    claims = verify_token(token)
    return claims.get("exp", 0)