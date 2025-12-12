# tests/runtime/test_runtime_sweep.py

import time
from runtime_registry import RuntimeRegistry

def test_runtime_sweep_transitions():
    rr = RuntimeRegistry(stale_after=1, dead_after=2)

    rr.touch("ae-1")
    assert "ae-1" in rr.live

    time.sleep(1.2)
    rr.sweep()
    assert "ae-1" in rr.stale

    time.sleep(1.2)
    rr.sweep()
    assert "ae-1" in rr.dead
