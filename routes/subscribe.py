# # abi_service/routes/subscribe.py
import asyncio, json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from aegnix_core.logger import get_logger
from bus import bus

router = APIRouter()
log = get_logger("ABI.Subscribe", to_file="logs/abi_service.log")

# Active subscribers per topic
subscribers: dict[str, set[asyncio.Queue]] = {}


async def event_stream(topic: str):
    """Async generator yielding SSE-formatted events for a given topic."""
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
async def subscribe_topic(request: Request, topic: str):
    """
    SSE endpoint for AE developers or agents to stream messages in real time.
    """
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
# Bridge: connect internal bus → SSE subscribers
# ---------------------------------------------------------------------
# _main_loop = asyncio.get_event_loop()
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
    if _main_loop.is_closed():
        return
    # Schedule coroutine in the FastAPI event loop
    _main_loop.call_soon_threadsafe(
        lambda: asyncio.create_task(_broadcast_to_sse(topic, message))
    )

# Register as a proper async handler so bus.publish can await it


async def _bridge_handler(topic: str, message: dict):
    _safe_broadcast(topic, message)

bus._handlers.append(_bridge_handler)




# import asyncio, json, time
# from fastapi import APIRouter, Request
# from fastapi.responses import StreamingResponse
# from aegnix_core.logger import get_logger
# from bus import bus
#
# router = APIRouter()
# log = get_logger("ABI.Subscribe", to_file="logs/abi_service.log")
#
# # Maintain active connections per topic
# subscribers: dict[str, set[asyncio.Queue]] = {}
#
# async def event_stream(topic: str):
#     """
#     Async generator that yields SSE-formatted events for a topic.
#     Each connected client gets its own queue and loop reference.
#     """
#     queue = asyncio.Queue()
#     loop = asyncio.get_running_loop()
#     subscribers.setdefault(topic, set()).add((queue, loop))   # store both queue + loop
#     log.info(f"[SSE] Client subscribed to {topic}")
#     try:
#         while True:
#             msg = await queue.get()
#             print(f"[SSE DEBUG] event_stream({topic}) received msg: {msg}")
#             yield f"data: {json.dumps(msg)}\n\n"
#     except asyncio.CancelledError:
#         log.info(f"[SSE] Client disconnected from {topic}")
#     finally:
#         subscribers[topic].discard((queue, loop))
#
# # async def event_stream(topic: str):
# #     """
# #     Async generator that yields SSE-formatted events for a topic.
# #     Each connected client gets its own queue.
# #     """
# #     queue = asyncio.Queue()
# #     subscribers.setdefault(topic, set()).add(queue)
# #     log.info(f"[SSE] Client subscribed to {topic}")
# #     try:
# #         while True:
# #             msg = await queue.get()
# #             print(f"[SSE DEBUG] event_stream({topic}) received msg: {msg}")
# #             yield f"data: {json.dumps(msg)}\n\n"
# #     except asyncio.CancelledError:
# #         log.info(f"[SSE] Client disconnected from {topic}")
# #     finally:
# #         subscribers[topic].discard(queue)
#
# @router.get("/{topic}")
# async def subscribe_topic(request: Request, topic: str):
#     async def heartbeat():
#         while True:
#             await asyncio.sleep(15)
#             yield "data: {\"ping\": \"keepalive\"}\n\n"
#
#     stream = event_stream(topic)
#
#     async def merged():
#         heartbeat_task = asyncio.create_task(heartbeat().__anext__())
#         async for chunk in stream:
#             yield chunk
#             if heartbeat_task.done():
#                 heartbeat_task = asyncio.create_task(heartbeat().__anext__())
#
#     return StreamingResponse(merged(), media_type="text/event-stream")
#
#
# # ---------------------------------------------------------------------
# # Hook bus to push messages into subscriber queues
# # ---------------------------------------------------------------------
# @bus.subscribe("*")
# async def broadcast_message(topic: str, payload: dict):
#     """
#     Receive messages from internal bus and fan them out to SSE clients.
#     """
#     if topic not in subscribers:
#         return
#
#     for queue, loop in list(subscribers[topic]):
#         try:
#             # ensure enqueue occurs in the correct event loop
#             loop.call_soon_threadsafe(queue.put_nowait, payload)
#             print(f"[SSE DEBUG] Queued message for {topic} on loop {id(loop)}: {payload}")
#         except Exception as e:
#             log.error(f"[SSE broadcast error] {e}")
#
# # @bus.subscribe("*")
# # async def broadcast_message(topic: str, payload: dict):
# #     """
# #     Receive messages from internal bus and fan them out to SSE clients.
# #     """
# #     if topic not in subscribers:
# #         return
# #
# #     for queue in list(subscribers[topic]):
# #         try:
# #             loop = asyncio.get_running_loop()
# #             # thread-safe enqueue into the FastAPI loop
# #             loop.call_soon_threadsafe(queue.put_nowait, payload)
# #             print(f"[SSE DEBUG] Queued message for {topic}: {payload}")
# #         except Exception as e:
# #             log.error(f"[SSE broadcast error] {e}")
#
#
# # @bus.subscribe("*")   # wild-card hook (pseudo-code, adjust to your bus)
# # async def broadcast_message(topic: str, payload: dict):
# #     """
# #     Receive messages from internal bus and fan them out to SSE clients.
# #     """
# #     if topic not in subscribers:
# #         return
# #     for queue in list(subscribers[topic]):
# #         try:
# #             queue.put_nowait(payload)
# #         except Exception as e:
# #             log.error(f"[SSE broadcast error] {e}")
#
#
#
# # # abi_service/routes/subscribe.py
# # import json, asyncio
# # from fastapi import APIRouter, Request, HTTPException
# # from starlette.responses import StreamingResponse
# # from aegnix_core.logger import get_logger
# # from bus import bus  # path as per your layout
# #
# # router = APIRouter()
# # log = get_logger("ABI.SSE")
# #
# # @router.get("/subscribe/{topic}")
# # async def sse_topic(topic: str, request: Request):
# #     """
# #     Server-Sent Events stream for a topic.
# #     Each ABI 'emit' will be fanned out here during local dev.
# #     """
# #     q = bus.subscribe(topic)
# #
# #     async def event_stream():
# #         try:
# #             while True:
# #                 # client disconnected?
# #                 if await request.is_disconnected():
# #                     break
# #                 msg = await q.get()
# #                 # SSE format
# #                 yield f"data: {json.dumps(msg)}\n\n"
# #         except asyncio.CancelledError:
# #             pass
# #
# #     headers = {
# #         "Cache-Control": "no-cache",
# #         "Connection": "keep-alive",
# #         "X-Accel-Buffering": "no",
# #     }
# #     return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
