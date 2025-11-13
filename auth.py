# abi_service/auth.py
"""
ABI Authentication Utilities
--------------------------------------

This module implements lightweight JSON Web Token (JWT) utilities
for the AEGNIX ABI Service.  It provides a minimal authentication layer
that issues and verifies session tokens for registered Atomic Experts (AEs).

These tokens form the **session integrity backbone**.

Purpose
-------
1.  Generate JWTs (`issue_token`) when an AE successfully completes
    the dual-crypto admission handshake.
2.  Verify JWTs (`verify_token`) for subsequent secured routes
    (e.g., /emit), ensuring the caller is an authenticated AE
    operating within an active session.

Token Structure
---------------
Each token encodes three claims:

    sub:  AE identifier (string)
    sid:  Session identifier (UUID string)
    exp:  Expiration timestamp (UTC, default 24 hours)

Example payload:

    {
        "sub": "fusion-ae",
        "sid": "c1b06e64-7c55-4e91-8af7-f52c49a50f3f",
        "exp": 1730867253
    }

The token is signed using an HMAC key provided via the
`ABI_JWT_SECRET` environment variable.

Integration Points
------------------
• `emit.py`  → uses `verify_token()` to authenticate messages
• `register.py` → uses `issue_token()` to grant a token upon admission

Environment Variables
---------------------
ABI_JWT_SECRET : str
    Secret key used to sign and verify JWTs.
    Default: "change_me" (for development only)

Raises
------
HTTPException(401)
    If the token is expired or invalid.

References
----------
• RFC 7519 – JSON Web Token (JWT)
• Framework Dev Phase 3F – Verified Emission & Session Integrity
"""
import os, jwt, datetime
from fastapi import HTTPException

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

# Secret key used for signing and verifying JWTs.
# Loaded from environment
SECRET = os.getenv("ABI_JWT_SECRET", "change_me")


# ---------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------
def issue_token(ae_id: str, session_id: str, ttl_seconds: int = 86400):
    """
     Issue a signed JWT for a registered AE session.

     Args:
         ae_id: Unique identifier of the AE (subject).
         session_id: Unique session identifier associated with this AE instance.
         ttl_seconds: Token lifetime in seconds. Default is 24 hours.

     Returns:
         str: Encoded JWT string.

     Example:
         >>> token = issue_token("fusion-ae", "uuid-1234")
         >>> print(token)
         'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
     """
    payload = {
        "sub": ae_id,
        "sid": session_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def verify_token(token: str):
    """
      Verify a JWT and return its decoded claims.

      Args:
          token: JWT string provided in the Authorization header.

      Returns:
          dict: Decoded payload containing `sub`, `sid`, and `exp`.

      Raises:
          HTTPException(401): If the token is expired or invalid.

      Example:
          >>> claims = verify_token(token)
          >>> claims["sub"]
          'fusion-ae'
      """
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
