"""
ABI Service: Audit Route
Receives and logs signed audit events using the unified AEGNIX logger.
"""


from fastapi import APIRouter, Request
from aegnix_core.utils import now_ts
from aegnix_core.logger import get_logger


router = APIRouter()
log = get_logger("ABI.Service", to_file="logs/abi_service.log")

@router.post("/")
async def append_audit(req: Request):
    """Append a signed audit event to local storage."""
    payload = await req.json()
    event_type = payload.get("event_type", "generic_event")
    entry = {
        "ts": now_ts(),
        "event_type": event_type,
        "payload": payload,
    }
    log.info(entry)
    return {"status": "logged", "event_type": event_type}

@router.get("/")
def list_audit(limit: int = 20):
    """
    Retrieve recent log entries (mocked for now).
    In production, this would tail from file or DB.
    """
    log.info({"route": "list_audit", "limit": limit})
    return {"events": [f"Mock audit event {i}" for i in range(1, limit + 1)]}
