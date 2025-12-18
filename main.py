# abi_service : main.py Phase 3G
import sys
print("Loaded modules:", list(sys.modules.keys()))

from fastapi import FastAPI
import os, threading, time, yaml
from pathlib import Path
from bus import bus

from aegnix_core.storage import load_storage_provider
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.admission import AdmissionService
from aegnix_abi.policy import PolicyEngine
from aegnix_core.logger import get_logger


from routes import admin, admin_reflection, audit, session, register, emit, subscribe, ae_heartbeat,capabilities as capabilities_route
# from routes import emit as emit_route

from runtime_registry import RuntimeRegistry
from abi_state import ABIState
from routes import admin_runtime



# ------------------------------------------------------------------------------
# Init
# ------------------------------------------------------------------------------

app = FastAPI(title="AEGNIX ABI Service")
os.makedirs("logs", exist_ok=True)
os.makedirs("db", exist_ok=True)

log = get_logger("ABI.Service", to_file="logs/abi_service.log")

# Consistent DB path
DB_PATH = "db/abi_state.db"

# store = SQLiteStorage(DB_PATH)
store = load_storage_provider()
# store = load_storage_provider({"provider": "sqlite", "sqlite_path": DB_PATH})
# keyring = ABIKeyring(db_path=DB_PATH)
keyring = ABIKeyring(store)
emit.keyring = keyring
subscribe.keyring = keyring
admission = AdmissionService(keyring)

BASE_DIR = os.path.dirname(__file__)
STATIC_POLICY_PATH = Path(os.path.join(BASE_DIR, "config", "policy.yaml"))
SPP_PATH = Path(os.path.join(BASE_DIR, "config", "purpose_policy.yaml"))

# ------------------------------------------------------------------------------
# Swarm Purpose Policy Loader
# ------------------------------------------------------------------------------
def load_spp():
    try:
        return yaml.safe_load(SPP_PATH.read_text()) or {}
    except Exception as e:
        log.error(f"[ABI] Failed to load SPP: {e}")
        return {}
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
    emit.policy = engine

    # Update subscribe route
    subscribe.policy = engine

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
# Start sweeper thread
# ------------------------------------------------------------------------------
def start_runtime_sweeper(runtime_registry, interval: int = 5):
    logged_stale = set()
    logged_dead = set()

    def _sweeper():
        nonlocal logged_stale, logged_dead

        while True:
            try:
                runtime_registry.sweep()

                # --- log stale only when newly stale ---
                stale_now = set(runtime_registry.stale.keys())
                new_stale = stale_now - logged_stale
                if new_stale:
                    log.info({"event": "runtime_sweep_stale", "ae_ids": list(new_stale)})
                    logged_stale |= new_stale

                # Remove recovered from logged set (optional)
                logged_stale &= stale_now

                # --- log dead only when newly dead ---
                dead_now = set(runtime_registry.dead.keys())
                new_dead = dead_now - logged_dead
                if new_dead:
                    log.info({"event": "runtime_sweep_dead", "ae_ids": list(new_dead)})
                    logged_dead |= new_dead

                # If a dead AE ever returns (heartbeat), allow it to log again
                logged_dead &= dead_now

            except Exception as e:
                log.error({"event": "runtime_sweep_error", "error": str(e)})

            time.sleep(interval)

    t = threading.Thread(target=_sweeper, daemon=True)
    t.start()


@app.on_event("startup")
async def startup():
    import asyncio
    from reflection.sink import ReflectionSink
    from reflection.store import InMemoryReflectionStore

    reflection_store = InMemoryReflectionStore()
    reflection_sink = ReflectionSink(reflection_store)

    # -------------------------------
    # Load Swarm Purpose Policy
    # -------------------------------
    spp = load_spp()
    log.info("[ABI] Swarm Purpose Policy loaded", extra={"spp": spp})

    # Subscribe sink to runtime events
    if hasattr(bus, "subscribe"):
        bus.subscribe("ae.runtime")(lambda t, m: reflection_sink.on_event(t, m))
        bus.subscribe("abi.runtime.transition")(lambda t, m: reflection_sink.on_event(t, m))
    log.info("ReflectionSink subscribed to ae.runtime and abi.runtime.transition")

    subscribe.set_main_loop(asyncio.get_running_loop())

    # ----------------------------------------------------------
    # Create SessionManager & Runtime
    # ----------------------------------------------------------
    from sessions import SessionManager
    session_manager = SessionManager(store)
    # runtime = RuntimeRegistry()

    # ----------------------------------------------------------
    # Build ABI State Object
    # ----------------------------------------------------------
    global state
    state = ABIState(
        keyring=keyring,
        session_manager=session_manager,
        spp=spp,
        bus=bus,
        policy=policy_engine
    )

    log.info("[ABI] Effective SPP attached to state", extra={"spp": state.spp})

    # extract runtime registry
    runtime = state.runtime_registry

    # Start runtime sweeper (Phase 4B - Step 1)
    start_runtime_sweeper(runtime)

    # ----------------------------------------------------------
    # Inject state into routes
    # ----------------------------------------------------------
    register.session_manager = session_manager
    register.abi_state = state

    session.session_manager = session_manager
    session.abi_state = state


    emit.session_manager = session_manager
    emit.abi_state = state

    subscribe.session_manager = session_manager
    subscribe.abi_state = state

    capabilities_route.session_manager = session_manager
    capabilities_route.abi_state = state

    # Admin runtime views
    admin_runtime.abi_state = state

    log.info("ABI Service started with unified state (SessionManager + RuntimeRegistry)")
    log.info(f"Static Policy Path: {STATIC_POLICY_PATH}")

    ae_heartbeat.session_manager = session_manager
    ae_heartbeat.abi_state = state

    # ----------------------------------------------------------
    # Start policy watcher thread
    # ----------------------------------------------------------
    threading.Thread(target=watch_policy, daemon=True).start()

# ------------------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------------------

app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(admin_reflection.router, prefix="/admin/reflect")
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(register.router, tags=["register"])
app.include_router(emit.router, prefix="/emit", tags=["emit"])
app.include_router(subscribe.router, prefix="/subscribe", tags=["subscribe"])
app.include_router(capabilities_route.router, tags=["capabilities"])
app.include_router(session.router, prefix="/session", tags=["session"])
app.include_router(admin_runtime.router, prefix="/admin/runtime", tags=["runtime"])
app.include_router(ae_heartbeat.router, tags=["runtime"])



@app.get("/healthz")
@app.get("/healthz/")
def health():
    return {"status": "ok"}
