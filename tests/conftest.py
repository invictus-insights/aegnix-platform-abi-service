# Ensures local imports (e.g. from main import app) work
import sys, os
import pytest
from typing import Optional
from aegnix_core.storage import SQLiteStorage, KeyRecord


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

TEST_AE_ID = "test_sse_ae"
TEST_PUB = "yqqo8SjJfJrSbah69A2t2xrU4VQl7zp42QKbFZRyod8="


# @pytest.fixture(scope="session", autouse=True)
# def setup_test_ae():
#     # MUST match ABI’s real DB
#     store = SQLiteStorage("db/abi_state.db")
#
#     # Insert or update AE record
#     store.upsert_key(KeyRecord(
#         ae_id=TEST_AE_ID,
#         pubkey_b64=TEST_PUB,
#         roles="subscriber",
#         status="trusted",
#         expires_at=None
#     ))
#
#     yield


@pytest.fixture(autouse=True)
def reset_bus_state():
    """
    Reset the in-memory EventBus between tests so that handlers
    and queues from one test do not bleed into another.

    This matches the real behavior (long-lived bus) but gives us
    deterministic isolation in the test suite.
    """
    from bus import bus

    # Best-effort defensive clear; only in test context.
    for attr in ("_handlers", "handlers"):
        if hasattr(bus, attr):
            getattr(bus, attr).clear()
    for attr in ("_queues", "queues"):
        if hasattr(bus, attr):
            getattr(bus, attr).clear()

    yield

    # clean again after the test
    for attr in ("_handlers", "handlers"):
        if hasattr(bus, attr):
            getattr(bus, attr).clear()
    for attr in ("_queues", "queues"):
        if hasattr(bus, attr):
            getattr(bus, attr).clear()