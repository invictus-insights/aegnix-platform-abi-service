from fastapi import FastAPI
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.admission import AdmissionService
from aegnix_abi.policy import PolicyEngine
from aegnix_core.logger import get_logger
from routes import admin, audit, register, emit, subscribe
from routes import emit as emit_route
import os, threading, time


app = FastAPI(title="AEGNIX ABI Service")

os.makedirs("logs", exist_ok=True)

# --- Initialize keyring and admission service ---
keyring = ABIKeyring(db_path="db/abi_state.db")
emit.keyring = keyring  # inject the shared instance
admission = AdmissionService(keyring)

# --- Load initial policy from YAML ---
BASE_DIR = os.path.dirname(__file__)
POLICY_PATH = os.path.join(BASE_DIR, "config", "policy.yaml")
emit_route.policy = PolicyEngine.from_yaml(POLICY_PATH)

# policy = PolicyEngine.from_yaml(POLICY_PATH)
# policy = PolicyEngine()
log = get_logger("ABI.Service", to_file="logs/abi_service.log")


# Routers
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(register.router, tags=["register"])
app.include_router(emit.router, prefix="/emit", tags=["emit"])
app.include_router(subscribe.router, prefix="/subscribe", tags=["subscribe"])


# --- Hot-reload watcher thread ---
def watch_policy(path=POLICY_PATH, interval=10):
    """Background watcher that reloads policy.yaml if it changes."""
    last_mtime = 0
    while True:
        try:
            mtime = os.path.getmtime(path)
            if mtime != last_mtime:
                emit_route.policy = PolicyEngine.from_yaml(path)
                log.info(f"[ABI] Reloaded policy from {path} at {time.strftime('%X')}")
                last_mtime = mtime
        except Exception as e:
            log.error(f"[ABI] Policy watcher error: {e}")
        time.sleep(interval)


# --- Startup event ---
@app.on_event("startup")
async def startup():
    import asyncio

    # --- Initialize the SSE loop ---
    subscribe.set_main_loop(asyncio.get_running_loop())
    log.info("ABI Service started with SQLite state")
    log.info(f"Loaded policy from {POLICY_PATH}")

    threading.Thread(target=watch_policy, daemon=True).start()

# @app.on_event("startup")
# async def startup():
#     import asyncio
#     subscribe.set_main_loop(asyncio.get_running_loop())
#     log.info("ABI Service started with SQLite state")

@app.get("/healthz")
def health():
    return {"status": "ok"}
