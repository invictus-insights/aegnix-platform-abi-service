"""
ABI Service — Emit Route
Receives signed envelopes from AE clients and dispatches them
to the proper transport adapter (Pub/Sub, Kafka, or Local relay).
"""
# import sys, io
from fastapi import APIRouter, Request, HTTPException
from aegnix_core.logger import get_logger
from aegnix_core.utils import now_ts
from aegnix_abi.policy import PolicyEngine
from aegnix_abi.audit import AuditLogger


# try:
#     # type: ignore[attr-defined]
#     sys.stdout.reconfigure(encoding="utf-8")
#     sys.stderr.reconfigure(encoding="utf-8")
# except Exception:
#     # Fallback for environments that don't support reconfigure
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
#     sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

router = APIRouter()
log = get_logger("ABI.Emit", to_file="logs/abi_service.log")

# Core components
policy = PolicyEngine()
audit = AuditLogger(file_path="logs/abi_audit.log")

# Placeholder registry of transport backends (Phase 3)
TRANSPORTS = {
    # "local": lambda topic, msg: log.info(f"[LOCAL DISPATCH] {topic} → {str(msg)[:120]}"),
    "local": lambda topic, msg: log.info(f"[LOCAL DISPATCH] {topic} -> {str(msg)[:120]}"),

    # "pubsub": PubSubAdapter(...),
    # "kafka": KafkaAdapter(...),
}


@router.post("/")
async def emit_message(req: Request):
    """
    Accepts a signed envelope from an AE client.
    Validates policy, logs, and dispatches to transports.
    """
    try:
        envelope = await req.json()
        subject = envelope.get("subject")
        producer = envelope.get("producer")
        ts = now_ts()

        if not subject or not producer:
            raise HTTPException(status_code=400, detail="Missing subject or producer")

        # Policy validation
        if not policy.can_publish(subject, producer):
            log.warning({"event": "emit_blocked", "subject": subject, "producer": producer})
            raise HTTPException(status_code=403, detail="Publish not allowed by policy")

        # Audit entry
        audit.log_event("emit_received", {
            "subject": subject,
            "producer": producer,
            "ts": ts,
            "labels": envelope.get("labels", []),
        })

        # Dispatch to all active transports
        for name, transport in TRANSPORTS.items():
            try:
                transport(subject, envelope)
            except Exception as e:
                log.error(f"[{name}] dispatch error: {e}")

        log.info({
            "event": "emit_processed",
            "subject": subject,
            "producer": producer,
            "transports": list(TRANSPORTS.keys()),
        })

        return {"status": "accepted", "subject": subject, "ts": ts}

    except Exception as e:
        log.error({"event": "emit_error", "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
