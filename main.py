from fastapi import FastAPI
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.admission import AdmissionService
from aegnix_abi.policy import PolicyEngine
from aegnix_core.logger import get_logger
from routes import admin, audit, register, emit
import os

app = FastAPI(title="AEGNIX ABI Service")

os.makedirs("logs", exist_ok=True)

keyring = ABIKeyring(db_path="db/abi_state.db")
admission = AdmissionService(keyring)
policy = PolicyEngine()
log = get_logger("ABI.Service", to_file="logs/abi_service.log")


# Routers
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(register.router, prefix="/register", tags=["register"])
app.include_router(emit.router, prefix="/emit", tags=["emit"])

@app.on_event("startup")
def startup():
    log.info("ABI Service started with SQLite state")

@app.get("/healthz")
def health():
    return {"status": "ok"}
