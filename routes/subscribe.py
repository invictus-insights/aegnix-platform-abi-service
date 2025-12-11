# abi_service/routes/subscribe.py
import asyncio, json
from typing import cast
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import StreamingResponse
from aegnix_core.logger import get_logger
from bus import bus
from auth import verify_token
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.policy import PolicyEngine
from runtime_registry import RuntimeRegistry
router = APIRouter()
log = get_logger("ABI.Subscribe", to_file="logs/abi_service.log")

# injected from main.py
runtime_registry: RuntimeRegistry = cast(RuntimeRegistry, None)
session_manager = None

keyring: ABIKeyring = cast(ABIKeyring, None)
policy: PolicyEngine = cast(PolicyEngine, None)


# topic → set of asyncio.Queue
subscribers: dict[str, set[asyncio.Queue]] = {}

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop):
    global _main_loop
    _main_loop = loop


# -------------------------------------------------------------------
# Bus → SSE bridge
# -------------------------------------------------------------------
async def _broadcast_to_sse(topic: str, payload: dict):
    if topic not in subscribers:
        return
    for q in list(subscribers[topic]):
        try:
            q.put_nowait(payload)
        except Exception as e:
            log.error(f"[SSE broadcast error] {e}")


def _safe_broadcast(topic: str, message: dict):
    global _main_loop
    if _main_loop is None or _main_loop.is_closed():
        return

    _main_loop.call_soon_threadsafe(
        lambda: asyncio.create_task(_broadcast_to_sse(topic, message))
    )


async def _bridge_handler(topic: str, message: dict):
    _safe_broadcast(topic, message)


# -------------------------------------------------------------------
# SSE Streaming Core with Heartbeats
# -------------------------------------------------------------------
async def sse_stream(request: Request, topic: str):
    """
    Main SSE stream generator with:
        - per-client asyncio.Queue
        - 10s heartbeat
        - queue draining
        - proper cleanup on disconnect
    """
    queue = asyncio.Queue()

    # Register queue
    subscribers.setdefault(topic, set()).add(queue)
    bus.add_queue(topic, queue)

    log.info(f"[SSE] Client subscribed to {topic}")

    try:
        while True:
            if await request.is_disconnected():
                break

            try:
                # Wait for message or timeout for heartbeat
                payload = await asyncio.wait_for(queue.get(), timeout=10.0)

                # Send JSON message
                yield f"data: {json.dumps(payload)}\n\n"

            except asyncio.TimeoutError:
                # 10 second heartbeat (comment line)
                yield ": heartbeat\n\n"

    except asyncio.CancelledError:
        log.info(f"[SSE] Cancelled client for topic={topic}")

    finally:
        # Cleanup
        subscribers[topic].discard(queue)
        bus.remove_queue(topic, queue)
        log.info(f"[SSE] Client disconnected from {topic}")


# -------------------------------------------------------------------
# API Route
# -------------------------------------------------------------------
@router.get("/{topic}")
@router.get("/{topic}/")
async def subscribe_topic(request: Request,
                          topic: str,
                          authorization: str | None = Header(default=None)):

    if keyring is None or policy is None:
        raise HTTPException(status_code=500, detail="ABI not initialized")

    # ---------------- JWT ----------------
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]

    try:
        claims = verify_token(token)
        ae_id = claims.get("sub")

        session_id = claims.get("sid")

        jwt_roles = claims.get("roles", "")

        # Track AE liveness
        runtime_registry.touch(ae_id, session_id=session_id)

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # ---------------- Keyring lookup ----------------
    rec = keyring.get_by_aeid(ae_id)
    # rec = keyring.get_key(ae_id)
    if not rec:
        raise HTTPException(status_code=403, detail="AE not found in keyring")
    if rec.status != "trusted":
        raise HTTPException(status_code=403, detail="AE not trusted")

    # Merge roles
    effective_roles = rec.roles or jwt_roles

    # ---------------- Policy enforcement ----------------
    if not policy.can_subscribe(ae_id, topic, roles=effective_roles):
        raise HTTPException(status_code=403, detail="Policy denied subscribe")

    # ---------------- Bus handler registration ----------------
    handler_id = f"_bridge_{topic}"
    for h in bus._handlers:
        if getattr(h, "_handler_id", None) == handler_id:
            break
    else:
        @bus.subscribe(topic)
        async def _bridge(t, msg):
            await _bridge_handler(t, msg)

        _bridge._handler_id = handler_id
        log.info(f"[SSE] Bus bridge registered for topic={topic}")

    # ---------------- Build SSE Response ----------------
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return StreamingResponse(sse_stream(request, topic),
                             media_type="text/event-stream",
                             headers=headers)
