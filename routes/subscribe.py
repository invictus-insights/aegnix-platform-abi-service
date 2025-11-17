# # abi_service/routes/subscribe.py
import asyncio, json
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import StreamingResponse
from aegnix_core.logger import get_logger
from bus import bus
from auth import verify_token
from aegnix_abi.keyring import ABIKeyring
from aegnix_abi.policy import PolicyEngine

keyring: ABIKeyring | None = None
policy: PolicyEngine | None = None

router = APIRouter()
log = get_logger("ABI.Subscribe", to_file="logs/abi_service.log")

# Active subscribers per topic
subscribers: dict[str, set[asyncio.Queue]] = {}


async def event_stream(topic: str):
    """"""
    queue = asyncio.Queue()
    subscribers.setdefault(topic, set()).add(queue)
    log.info(f"[SSE] Client subscribed to {topic}")

    try:
        while True:
            msg = await queue.get()
            yield f"data: {json.dumps(msg)}\n\n"
    except asyncio.CancelledError:
        log.info(f"[SSE] Client disconnected from {topic}")
    finally:
        subscribers[topic].discard(queue)


@router.get("/{topic}")
async def subscribe_topic(request: Request, topic: str, authorization: str | None = Header(default=None)):
    """
    SSE endpoint for AE developers or agents to stream messages in real time.
    """
    if keyring is None or policy is None:
        raise HTTPException(status_code=500, detail="ABI not initialized")

    # --- JWT Authentication ---
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]

    try:
        claims = verify_token(token)
        ae_id = claims.get("sub")
        jwt_roles = claims.get("roles", "")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # --- Keyring lookup (authoritative roles) ---
    rec = keyring.get_key(ae_id)
    if not rec:
        raise HTTPException(status_code=403, detail="AE not found in keyring")

    if rec.status != "trusted":
        raise HTTPException(status_code=403, detail="AE not trusted")

    # --- Step 3.3 Role Merge ---
    effective_roles = rec.roles or jwt_roles

    # --- Policy Enforcement for Subscribe ---
    if not policy.can_subscribe(ae_id, topic, roles=effective_roles):
        raise HTTPException(status_code=403, detail="Policy denied subscribe")

    # SSE heartbeat + merging
    async def heartbeat():
        while True:
            await asyncio.sleep(15)
            yield "data: {\"ping\": \"keepalive\"}\n\n"

    async def merged():
        # Interleave topic messages and heartbeats
        stream = event_stream(topic)
        hb = heartbeat()
        done, pending = set(), set()
        while True:
            if await request.is_disconnected():
                break
            msg_task = asyncio.create_task(stream.__anext__())
            hb_task = asyncio.create_task(hb.__anext__())
            done, pending = await asyncio.wait(
                {msg_task, hb_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                try:
                    yield task.result()
                except StopAsyncIteration:
                    return
            for p in pending:
                p.cancel()

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(merged(), media_type="text/event-stream", headers=headers)


# ---------------------------------------------------------------------
# Bridge: bus → SSE subscribers
# ---------------------------------------------------------------------
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop):
    global _main_loop
    _main_loop = loop


async def _broadcast_to_sse(topic: str, payload: dict):
    """Push messages from the bus to any connected SSE subscribers."""
    if topic not in subscribers:
        return
    for q in list(subscribers[topic]):
        try:
            q.put_nowait(payload)
        except Exception as e:
            log.error(f"[SSE broadcast error] {e}")


def _safe_broadcast(topic: str, message: dict):
    """Thread-safe bridge from EventBus to the FastAPI loop."""
    global _main_loop
    if _main_loop is None or _main_loop.is_closed():
        # Skip if no loop (e.g., during pytest)
        return
    _main_loop.call_soon_threadsafe(
        lambda: asyncio.create_task(_broadcast_to_sse(topic, message))
    )


async def _bridge_handler(topic: str, message: dict):
    _safe_broadcast(topic, message)

bus._handlers.append(_bridge_handler)

