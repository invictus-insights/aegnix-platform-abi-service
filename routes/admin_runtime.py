#routes\admin_runtime.py

from fastapi import APIRouter
from typing import cast
from abi_state import ABIState

router = APIRouter()

# Injected in main.py
abi_state: ABIState = cast(ABIState, None)


@router.get("/live")
def live():
    return [
        abi_state.normalize_runtime_record(rec, ae_id=ae_id)
        for ae_id, rec in abi_state.get_live_agents().items()
    ]


@router.get("/stale")
def stale():
    return [
        abi_state.normalize_runtime_record(rec, ae_id=ae_id)
        for ae_id, rec in abi_state.get_stale_agents().items()
    ]


@router.get("/dead")
def dead():
    return [
        abi_state.normalize_runtime_record(rec, ae_id=ae_id)
        for ae_id, rec in abi_state.get_dead_agents().items()
    ]


@router.get("/{ae_id}")
def agent(ae_id: str):
    rec = abi_state.get_agent_state(ae_id)
    if not rec:
        return {"error": "AE not found"}
    return abi_state.normalize_runtime_record(rec, ae_id=ae_id)


@router.get("/all")
def get_all():
    return {
        "live": [
            abi_state.normalize_runtime_record(rec, ae_id=ae_id)
            for ae_id, rec in abi_state.get_live_agents().items()
        ],
        "stale": [
            abi_state.normalize_runtime_record(rec, ae_id=ae_id)
            for ae_id, rec in abi_state.get_stale_agents().items()
        ],
        "dead": [
            abi_state.normalize_runtime_record(rec, ae_id=ae_id)
            for ae_id, rec in abi_state.get_dead_agents().items()
        ],
    }

