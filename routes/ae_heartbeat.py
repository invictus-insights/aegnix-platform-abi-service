from typing import Optional, cast
from fastapi import APIRouter, Header, HTTPException
from aegnix_core.logger import get_logger
from auth import verify_token
from sessions import SessionManager
from abi_state import ABIState

router = APIRouter(prefix="/ae", tags=["runtime"])

log = get_logger("ABI.AEHeartbeat", to_file="logs/abi_service.log")

# injected from main.py
session_manager: SessionManager = None
abi_state: ABIState = cast(ABIState, None)


def _get_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1]


@router.post("/heartbeat")
@router.post("/heartbeat/")
def ae_heartbeat(authorization: Optional[str] = Header(None)):
    if session_manager is None:
        raise RuntimeError("SessionManager not initialized")

    token = _get_bearer_token(authorization)
    claims = verify_token(token)

    ae_id = claims.get("sub")
    sid = claims.get("sid")
    if not ae_id or not sid:
        raise HTTPException(status_code=400, detail="Token missing 'sub' or 'sid'")

    # Ensure session still valid
    session_manager.assert_session_active(sid)
    session_manager.touch(sid)  # keep session fresh too

    if abi_state is None:
        log.error({"event": "heartbeat_missing", "ae_id": ae_id, "session_id": sid})
    else:
        abi_state.heartbeat(ae_id=ae_id, session_id=sid, source="explicit")

    return {"ok": True, "ae_id": ae_id, "sid": sid}
