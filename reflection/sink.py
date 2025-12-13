# reflection/sink.py

from reflection.models import ReflectionEvent
from reflection.store import ReflectionStore
import time


class ReflectionSink:
    """
    Subscribes to runtime semantic events and records them.
    """

    def __init__(self, store: ReflectionStore):
        self.store = store

    def on_event(self, topic: str, payload: dict):
        """
        Generic handler for runtime events.
        """
        evt = self._normalize(topic, payload)
        if evt:
            self.store.append(evt)

    def _normalize(self, topic: str, payload: dict) -> ReflectionEvent | None:
        """
        Convert runtime/bus payload into ReflectionEvent.
        """
        now = time.time()

        if topic == "ae.runtime":
            return ReflectionEvent(
                event_type=topic,
                ae_id=payload.get("ae_id"),
                session_id=payload.get("session_id"),
                ts=payload.get("ts", now),
                source=payload.get("source"),
                intent=payload.get("intent"),
                subject=payload.get("subject"),
                quality=payload.get("quality"),
                meta=payload.get("meta"),
            )

        if topic == "abi.runtime.transition":
            return ReflectionEvent(
                event_type=topic,
                ae_id=payload.get("ae_id"),
                session_id=payload.get("session_id"),
                ts=payload.get("ts", now),
                from_state=payload.get("from_state"),
                to_state=payload.get("to_state"),
                meta=payload,
            )

        return None
