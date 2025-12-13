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
        abi_state._normalize_runtime_record(r)
        for r in abi_state.get_live_agents().values()
    ]


@router.get("/stale")
def stale():
    return [
        abi_state.normalize_runtime_record(r)
        for r in abi_state.get_stale_agents().values()
    ]


@router.get("/dead")
def dead():
    return [
        abi_state.normalize_runtime_record(r)
        for r in abi_state.get_dead_agents().values()
    ]


@router.get("/{ae_id}")
def agent(ae_id: str):
    rec = abi_state.get_agent_state(ae_id)
    if not rec:
        return {"error": "AE not found"}
    return abi_state.normalize_runtime_record(rec)


@router.get("/all")
def get_all():
    return {
        "live": [
            ABIState.normalize_runtime_record(r)
            for r in abi_state.get_live_agents().values()
        ],
        "stale": [
            ABIState.normalize_runtime_record(r)
            for r in abi_state.get_stale_agents().values()
        ],
        "dead": [
            ABIState.normalize_runtime_record(r)
            for r in abi_state.get_dead_agents().values()
        ],
    }

