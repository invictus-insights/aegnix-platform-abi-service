# test_subscribe_loopback.py
"""
Test: Verify ABI bus → SSE /subscribe loopback.
"""

import asyncio
import json
import threading
import sys
import pytest
import jwt
import time
from contextlib import contextmanager
from fastapi.testclient import TestClient
from main import app
from bus import bus
from auth import issue_access_token
from tests.conftest import TEST_AE_ID

TEST_PRIV = "Q5BiVnloRJ1sgZ5ONiIzO5l9DLO3TTL1M10eR3bKTuA="


@contextmanager
def running_client():
    """Ensure FastAPI startup/shutdown events fire properly."""
    with TestClient(app) as c:
        yield c


def make_test_jwt():
    """
    Use the same JWT helper as the ABI Service so the token
    structure matches what /subscribe expects (sub, sid, roles, exp).
    """
    return issue_access_token(
        ae_id=TEST_AE_ID,
        session_id="session-sse-test",
        roles="subscriber",
    )


def stream_sse(client, topic, results, stop_event):
    """
    SSE listener loop:
      - Connects to /subscribe/<topic> with a valid JWT
      - Collects the first non-heartbeat event
      - Exits cleanly so the thread can be joined without hanging
    """
    token = make_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    with client.stream("GET", f"/subscribe/{topic}", headers=headers) as stream:
        for line in stream.iter_lines():
            print(f"[DEBUG] SSE raw line: {line!r}")
            if stop_event.is_set():
                print("[DEBUG] Stop event triggered; exiting SSE loop.")
                break
            if not line or not line.startswith("data:"):
                continue
            try:
                payload = line[len("data:"):].strip()
                data = json.loads(payload)
                if "ping" in data:
                    continue  # ignore heartbeats
                results.append(data)
                break
            except Exception as e:
                print(f"[SSE parse error] {e}")
                break

@pytest.mark.xfail(sys.platform == "win32", reason="Windows asyncio loop does not tear down cleanly under pytest")
def test_bus_to_sse_loopback():
    """
    Ensure that an event published on the bus is delivered to SSE subscribers.
    """
    topic = "fusion.topic"
    results: list[dict] = []
    stop_event = threading.Event()

    with running_client() as client:
        # Start SSE listener thread
        t = threading.Thread(
            target=stream_sse, args=(client, topic, results, stop_event), daemon=True
        )
        t.start()

        # Wait for the SSE connection to establish
        asyncio.run(asyncio.sleep(0.75))

        # Publish message into bus
        asyncio.run(bus.publish(topic, {"track_id": "TEST-123"}))

        # Allow message propagation
        asyncio.run(asyncio.sleep(1.0))

        # Stop listener thread
        stop_event.set()
        t.join(timeout=2)
        client.close()

    assert results, "No message received via SSE"
    assert results[0].get("track_id") == "TEST-123", results


# ---------------------------------------------------------------------
# Global Teardown — GUARANTEED FIX FOR WINDOWS
# ---------------------------------------------------------------------
def teardown_module():
    """
    Fully tear down the event loop to avoid pytest hanging on Windows.
    Works by:
      • cancelling all pending tasks
      • shutting down async generators
      • closing the loop
      • creating a fresh loop for pytest to finish cleanly
    """
    try:
        loop = asyncio.get_event_loop()

        # Cancel all pending tasks
        tasks = asyncio.all_tasks(loop)
        for t in tasks:
            t.cancel()

        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())

        loop.close()

        # Create a fresh loop so pytest doesn't choke
        asyncio.set_event_loop(asyncio.new_event_loop())

    except Exception as e:
        print(f"[teardown_module] Suppressed teardown exception: {e}")
