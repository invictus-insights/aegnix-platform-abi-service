"""
Test: Verify ABI bus → SSE /subscribe loopback.
"""

import asyncio
import json
import threading
import jwt
import time
from contextlib import contextmanager
from fastapi.testclient import TestClient
from main import app
from bus import bus

TEST_PRIV = "Q5BiVnloRJ1sgZ5ONiIzO5l9DLO3TTL1M10eR3bKTuA="


def make_test_jwt():
    # NOTE: ABI uses symmetric HS256 or your configured algorithm
    payload = {
        "sub": "test_sse_ae",
        "roles": "subscriber",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    return jwt.encode(payload, "mydevsecret123", algorithm="HS256")

@contextmanager
def running_client():
    """Ensure FastAPI startup/shutdown events fire properly."""
    with TestClient(app) as c:
        yield c


def stream_sse(client, topic, results, stop_event):
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


def test_bus_to_sse_loopback():
    """
    Ensure that an event published on the bus is delivered to SSE subscribers.
    """
    topic = "fusion.topic"
    results = []
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

    # Validate receipt
    assert results, "No message received via SSE"
    assert results[0].get("track_id") == "TEST-123", results
