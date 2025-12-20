# reflection/sink.py

from reflection.models import (
    ReflectionRecord,
    Correlation,
    Transition,
)
from reflection.store import ReflectionStore
import time


class ReflectionSink:
    """
    Subscribes to runtime semantic events and records them.
    """

    def __init__(self, store: ReflectionStore):
        self.store = store

    async def on_event(self, topic: str, payload: dict):
        """
        Generic handler for runtime records.
        """
        record = self._normalize(topic, payload)
        if record:
            self.store.append(record)

    def _normalize(self, topic: str, payload: dict) -> ReflectionRecord | None:
        """
        Convert runtime/bus payload into ReflectionRecord.
        """
        now = time.time()

        ae_id = payload.get("ae_id")
        session_id = payload.get("session_id")

        correlation = Correlation(
            ae_id=ae_id,
            session_id=session_id,
            confidence="high" if ae_id else "low",
        )

        if topic == "ae.runtime":
            return ReflectionRecord(
                domain="runtime",
                event_type=topic,
                ts=payload.get("ts", now),
                intent=payload.get("intent"),
                subject=payload.get("subject"),
                source={"type": "ae", "id": ae_id},
                correlation=correlation,
                quality=payload.get("quality"),
                payload=payload,
                labels={"topic": topic},
            )

        if topic == "abi.runtime.transition":
            transition = Transition(
                name="lifecycle",
                from_state=payload.get("from_state"),
                to_state=payload.get("to_state"),
                reason=payload.get("reason"),
                ts=payload.get("ts", now),
            )

            return ReflectionRecord(
                domain="abi",
                event_type=topic,
                ts=payload.get("ts", now),
                source={"type": "abi"},
                correlation=correlation,
                transitions=[transition],
                payload=payload,
                labels={"topic": topic},
            )

        return None
