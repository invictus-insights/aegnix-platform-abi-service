from fastapi import APIRouter
from typing import cast
from abi_state import ABIState

router = APIRouter()

# Injected in main.py
abi_state: ABIState = cast(ABIState, None)
   # Injected in main.py


@router.get("/live")
def get_live():
    return {"live": abi_state.get_live_agents()}


@router.get("/stale")
def get_stale():
    return {"stale": abi_state.get_stale_agents()}


@router.get("/all")
def get_all():
    return {
        "live": abi_state.get_live_agents(),
        "stale": abi_state.get_stale_agents()
    }
