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


@pytest.fixture(scope="session", autouse=True)
def setup_test_ae():
    # MUST match ABI’s real DB
    store = SQLiteStorage("db/abi_state.db")

    # Insert or update AE record
    store.upsert_key(KeyRecord(
        ae_id=TEST_AE_ID,
        pubkey_b64=TEST_PUB,
        roles="subscriber",
        status="trusted",
        expires_at=None
    ))

    yield