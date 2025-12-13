# abi_service/routes/session.py — Phase 4A: session refresh + heartbeat

from typing import Optional
from fastapi import APIRouter, HTTPException, Body, Header
from aegnix_core.logger import get_logger
from auth import verify_token, issue_access_token, ACCESS_TTL
from sessions import SessionManager
from abi_state import ABIState
from typing import cast

router = APIRouter()
log = get_logger("ABI.SessionRoutes")

# Injected from main.py
session_manager: SessionManager = None
# runtime_registry = None
abi_state: ABIState = cast(ABIState, None)

# --------------------------------------------------------------------------
# Helper: Extract Bearer <token>
# --------------------------------------------------------------------------
def _get_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1]


# ------------------------------------------------------------------------------
# POST /session/refresh
# ------------------------------------------------------------------------------
@router.post("/refresh")
@router.post("/refresh/")
def refresh_session(
    session_id: str = Body(..., embed=True),
    refresh_token: str = Body(..., embed=True),
):
    """
    Exchange refresh_token for a fresh access token,
    rotating the refresh token in the process.
    """
    if session_manager is None:
        raise RuntimeError("SessionManager not initialized in session routes")

    try:
        # 1. Validate refresh token hash + expiry
        token_rec = session_manager.validate_refresh_token(session_id, refresh_token)
        if not token_rec:
            log.warning(f"[SESSION] Invalid refresh token for sid={session_id}")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # 2. Ensure session is active
        session_manager.assert_session_active(session_id)

        # 3. Rotate refresh token
        new_raw, new_rec = session_manager.rotate_refresh_token(token_rec)

        # 4. Load session
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="Session not found")

        # 5. Issue new access token
        new_access = issue_access_token(
            ae_id=session.subject,
            session_id=session.id,
            roles=session.metadata.get("roles", "producer")
        )

        # 6. Touch session (update last_seen)
        session_manager.touch(session_id)

        log.info(f"[SESSION] Access token refreshed for sid={session_id}")

        return {
            "session_id": session_id,
            "access_token": new_access,
            "expires_in": ACCESS_TTL,
            "refresh_token": new_raw,
            "refresh_expires_in": new_rec.expires_at - new_rec.created_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[SESSION] refresh error for sid={session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal error during refresh")


# ------------------------------------------------------------------------------
# POST /session/heartbeat
# ------------------------------------------------------------------------------
@router.post("/heartbeat")
@router.post("/heartbeat/")
def heartbeat(
    authorization: Optional[str] = Header(None),
):
    """
    Touch session using current access token.
    Sliding idle window. no rotation.
    """
    if session_manager is None:
        raise RuntimeError("SessionManager not initialized in session routes")

    token = _get_bearer_token(authorization)
    claims = verify_token(token)

    sid = claims.get("sid")
    if not sid:
        raise HTTPException(status_code=400, detail="Missing 'sid' in token")

    try:
        # Validate active session
        session_manager.assert_session_active(sid)

        # last_seen_at
        session_manager.touch(sid)

        ae_id = claims.get("sub")

        if abi_state is None:
            log.error({
                "event": "heartbeat_missing",
                "ae_id": ae_id,
                "session_id": sid,
                "source": "session"
            })
        else:
            abi_state.heartbeat(
                ae_id=ae_id,
                session_id=sid,
                source="session"
            )

        return {"ok": True, "sid": sid}
    except ValueError as e:
        log.warning(f"[SESSION] heartbeat session invalid: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        log.error(f"[SESSION] heartbeat error: {e}")
        raise HTTPException(status_code=500, detail="Internal error during heartbeat")
