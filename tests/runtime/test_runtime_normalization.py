# tests/runtime/test_runtime_normalization.py

from abi_state import ABIState
from runtime_registry import RuntimeRegistry


class Dummy:
    """Minimal stub for unused ABIState dependencies"""
    pass


def test_runtime_normalization():
    # --- Arrange ---
    abi_state = ABIState(
        keyring=Dummy(),
        session_manager=Dummy(),
        bus=Dummy(),
        policy=Dummy(),
    )

    ae_id = "test_ae"
    session_id = "sid-123"

    # --- Act ---
    abi_state.heartbeat(
        ae_id=ae_id,
        session_id=session_id,
        source="emit",
        intent="publish",
        subject="fusion.topic",
        quality="normal",
        meta={"foo": "bar"},
    )

    rec = abi_state.get_agent_state(ae_id)
    # normalized = ABIState.normalize_runtime_record(rec)
    normalized = ABIState.normalize_runtime_record(rec, ae_id=ae_id)

    # --- Assert ---
    assert normalized["ae_id"] == ae_id
    assert normalized["session_id"] == session_id
    assert normalized["last_source"] == "emit"
    assert normalized["last_intent"] == "publish"
    assert normalized["last_subject"] == "fusion.topic"
    assert normalized["quality"] == "normal"
    assert normalized["heartbeat_count"] == 1
    assert normalized["meta"]["foo"] == "bar"
