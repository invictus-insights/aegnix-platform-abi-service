# abi_service/bus.py
import asyncio, inspect
from collections import defaultdict

from typing import Callable, Awaitable, Dict, List, Union

class EventBus:
    """Asynchronous in-memory event bus with decorator + queue support."""

    def __init__(self):
        self._topics: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._handlers: List[Callable[[str, dict], Awaitable[None]]] = []

    def subscribe(self, topic: str = None):
        """
        Supports:
          @bus.subscribe("topic")   -> register handler for one topic
          @bus.subscribe("*")       -> register wildcard handler
          @bus.subscribe            -> register wildcard handler
          q = bus.subscribe("topic")-> get asyncio.Queue for that topic
        """
        # No-arg decorator: @bus.subscribe
        if callable(topic):
            func = topic
            func._bus_topic = "*"
            self._handlers.append(func)
            return func

        # Arg-decorator: @bus.subscribe("topic") or @bus.subscribe("*")
        if isinstance(topic, str):
            def decorator(func):
                func._bus_topic = topic
                self._handlers.append(func)
                return func

            return decorator

        # Queue mode: bus.subscribe("topic")
        def queue_mode(t: str):
            q = asyncio.Queue()
            self._topics[t].append(q)
            return q

        return queue_mode


    async def publish(self, topic: str, message: dict):
        """Deliver event to local queues and registered handlers."""
        print(f"[BUS DEBUG] Publishing topic={topic}, message={message}")
        print(f"[BUS DEBUG] Queues: {len(self._topics.get(topic, []))}, Handlers: {len(self._handlers)}")

        # Deliver to local queues
        for q in list(self._topics.get(topic, [])):
            await q.put(message)
            print(f"[BUS DEBUG] → delivered to queue for {topic}")

        # Deliver to any decorator-based handlers
        for handler in list(self._handlers):
            handler_topic = getattr(handler, "_bus_topic", "*")
            print(f"[BUS DEBUG] Checking handler {handler.__name__} topic={handler_topic}")
            if handler_topic in ("*", topic):
                print(f"[BUS DEBUG] → invoking handler {handler.__name__} for {topic}")
                result = handler(topic, message)
                if inspect.isawaitable(result):
                    await result

    def add_queue(self, topic: str, queue: asyncio.Queue):
        """Public API: add an external queue (e.g., SSE queue) to a topic."""
        self._topics[topic].append(queue)

    def remove_queue(self, topic: str, queue: asyncio.Queue):
        """Public API: remove an external queue from a topic."""
        try:
            self._topics[topic].remove(queue)
        except ValueError:
            pass

# Create global bus instance
bus = EventBus()

