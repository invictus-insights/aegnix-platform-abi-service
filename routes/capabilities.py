# routes/capabilities.py
# routes/capabilities.py

from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Dict, Any

import yaml
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from aegnix_core.capabilities import AECapability
from aegnix_core.logger import get_logger
# from aegnix_core.storage import SQLiteStorage
from aegnix_core.storage import StorageProvider
from aegnix_abi.policy import PolicyEngine
from auth import verify_token  # same JWT verifier used by /emit

from runtime_registry import RuntimeRegistry
runtime_registry: RuntimeRegistry | None = None


router = APIRouter(prefix="/ae", tags=["capabilities"])

log = get_logger("ABI.Capabilities", to_file="logs/abi_service.log")

# These will be injected from main.py
# store: Optional[SQLiteStorage] = None
store: Optional[StorageProvider] = None
policy_engine: Optional[PolicyEngine] = None
STATIC_POLICY_PATH: Optional[Path] = None


class CapabilityRequest(BaseModel):
    publishes: List[str] = Field(default_factory=list)
    subscribes: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


def _load_static_subjects() -> Dict[str, Any]:
    """
    Helper: load static YAML policy to get the subject fence.
    """
    global STATIC_POLICY_PATH

    if STATIC_POLICY_PATH is None:
        return {"subjects": {}}

    try:
        data = yaml.safe_load(STATIC_POLICY_PATH.read_text()) or {}
        return data
    except Exception as e:
        log.error({"event": "capabilities_static_load_error", "error": str(e)})
        return {"subjects": {}}


@router.post("/capabilities")
@router.post("/capabilities/")
async def declare_capabilities(
    body: CapabilityRequest,
    authorization: str | None = Header(default=None),
):
    """
    AE capability declaration endpoint.

    Flow:
      1. Verify Bearer JWT via auth.verify_token
      2. Extract AE ID from `sub`
      3. Validate requested subjects are known to static policy
      4. Persist AECapability in SQLite
      5. Return current capability record

    Static policy remains the HARD FENCE:
      - Only subjects present in policy.yaml are accepted here
      - Actual enforcement still happens in PolicyEngine.can_publish/can_subscribe
    """
    global store, policy_engine

    if store is None:
        raise HTTPException(status_code=500, detail="Capability store not initialized")

    # --- Step 1: JWT verification ---
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]

    try:
        claims = verify_token(token)
    except HTTPException as e:
        log.error(
            {
                "event": "capabilities_jwt_invalid",
                "detail": e.detail,
                "token_prefix": token[:32],
            }
        )
        raise
    except Exception as e:
        log.error({"event": "capabilities_jwt_error", "error": str(e)})
        raise HTTPException(status_code=401, detail="Invalid token")

    ae_id = claims.get("sub")
    if not ae_id:
        raise HTTPException(status_code=401, detail="Token missing subject (sub)")

    # --- Runtime activity touch ---
    if runtime_registry is not None:
        runtime_registry.touch(ae_id, session_id=claims.get("sid"))

    log.info(
        {
            "event": "capabilities_request",
            "ae_id": ae_id,
            "publishes": body.publishes,
            "subscribes": body.subscribes,
        }
    )

    # --- Step 2: Static fence check (subject existence) ---
    static_policy = _load_static_subjects()
    known_subjects = set(static_policy.get("subjects", {}).keys())

    requested_subjects = set(body.publishes) | set(body.subscribes)
    unknown = sorted(s for s in requested_subjects if s not in known_subjects)

    if unknown:
        log.warning(
            {
                "event": "capabilities_unknown_subjects",
                "ae_id": ae_id,
                "unknown": unknown,
            }
        )
        raise HTTPException(
            status_code=400,
            detail=f"Unknown subjects in capability request: {', '.join(unknown)}",
        )

    # --- Step 3: Persist capability ---
    cap = AECapability(
        ae_id=ae_id,
        publishes=body.publishes,
        subscribes=body.subscribes,
        meta=body.meta,
    )

    store.upsert_capability(cap)
    log.info(
        {
            "event": "capabilities_updated",
            "ae_id": ae_id,
            "publishes": cap.publishes,
            "subscribes": cap.subscribes,
        }
    )

    # NOTE:
    # We rely on the background watcher (main.watch_policy) to rebuild the
    # effective PolicyEngine from static YAML + new capabilities. We don't
    # recompute here to avoid tight coupling.

    return {
        "status": "ok",
        "ae_id": ae_id,
        "capability": cap.to_dict(),
    }
