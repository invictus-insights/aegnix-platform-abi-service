# abi_service : main.py Phase 3G

from fastapi import FastAPI
import os, threading, time, yaml
from pathlib import Path

from aegnix_core.storage import SQLiteStorage
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.admission import AdmissionService
from aegnix_abi.policy import PolicyEngine
from aegnix_core.logger import get_logger

from routes import admin, audit, register, emit, subscribe, capabilities as capabilities_route
from routes import emit as emit_route


# ------------------------------------------------------------------------------
# Init
# ------------------------------------------------------------------------------

app = FastAPI(title="AEGNIX ABI Service")
os.makedirs("logs", exist_ok=True)
os.makedirs("db", exist_ok=True)

log = get_logger("ABI.Service", to_file="logs/abi_service.log")

# Consistent DB path
DB_PATH = "db/abi_state.db"

store = SQLiteStorage(DB_PATH)
keyring = ABIKeyring(db_path=DB_PATH)
emit.keyring = keyring
admission = AdmissionService(keyring)

BASE_DIR = os.path.dirname(__file__)
STATIC_POLICY_PATH = Path(os.path.join(BASE_DIR, "config", "policy.yaml"))


# ------------------------------------------------------------------------------
# Policy Loaders
# ------------------------------------------------------------------------------

def load_static_policy():
    try:
        return yaml.safe_load(STATIC_POLICY_PATH.read_text()) or {}
    except Exception as e:
        log.error(f"[ABI] Failed to load static policy YAML: {e}")
        return {"subjects": {}}


def build_effective_policy():
    """
    Merge:
      - static.yaml
      - dynamic capabilities (SQLite)
    """
    static = load_static_policy()
    caps = store.list_capabilities()

    engine = PolicyEngine(static_policy=static, ae_caps=caps)

    # Update emit route
    emit_route.policy = engine

    # Update capabilities route
    capabilities_route.policy_engine = engine

    return engine


# Initial load
policy_engine = build_effective_policy()
log.info(f"Loaded static policy from {STATIC_POLICY_PATH}")

# Inject shared state into capabilities route
capabilities_route.store = store
capabilities_route.STATIC_POLICY_PATH = STATIC_POLICY_PATH


# ------------------------------------------------------------------------------
# Hot Reload Thread
# ------------------------------------------------------------------------------

def watch_policy(interval=5):
    last_yaml_mtime = 0
    last_cap_snapshot = None

    while True:
        try:
            # Watch YAML
            yaml_mtime = os.path.getmtime(STATIC_POLICY_PATH)
            if yaml_mtime != last_yaml_mtime:
                last_yaml_mtime = yaml_mtime
                build_effective_policy()
                log.info(f"[ABI] Static policy reloaded (YAML changed)")

            # Watch capability table
            caps = store.list_capabilities()
            snapshot = tuple(
                (c.ae_id, tuple(c.publishes), tuple(c.subscribes), c.updated_at)
                for c in caps
            )
            if snapshot != last_cap_snapshot:
                last_cap_snapshot = snapshot
                build_effective_policy()
                log.info(f"[ABI] Dynamic capabilities updated")

        except Exception as e:
            log.error(f"[ABI] Policy watcher error: {e}")

        time.sleep(interval)


# ------------------------------------------------------------------------------
# Startup
# ------------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    import asyncio

    subscribe.set_main_loop(asyncio.get_running_loop())

    log.info("ABI Service started with unified SQLite state")
    log.info(f"Static Policy Path: {STATIC_POLICY_PATH}")

    threading.Thread(target=watch_policy, daemon=True).start()


# ------------------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------------------

app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(register.router, tags=["register"])
app.include_router(emit.router, prefix="/emit", tags=["emit"])
app.include_router(subscribe.router, prefix="/subscribe", tags=["subscribe"])
app.include_router(capabilities_route.router, tags=["capabilities"])


@app.get("/healthz")
def health():
    return {"status": "ok"}
