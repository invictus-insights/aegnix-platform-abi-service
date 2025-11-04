"""
Test: Verify ABI bus → SSE /subscribe loopback.
"""

import asyncio
import json
import threading
from contextlib import contextmanager
from fastapi.testclient import TestClient
from main import app
from bus import bus


@contextmanager
def running_client():
    """Ensure FastAPI startup/shutdown events fire properly."""
    with TestClient(app) as c:
        yield c


def stream_sse(client: TestClient, topic: str, results: list, stop_event: threading.Event):
    """
    Blocking helper: read from the SSE endpoint until a message arrives or stop_event is set.
    Runs in a thread so pytest main loop can await bus.publish().
    """
    print(f"[DEBUG] Connecting to /subscribe/{topic}")
    with client.stream("GET", f"/subscribe/{topic}") as stream:
        print(f"[DEBUG] SSE connection established → /subscribe/{topic}")
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
