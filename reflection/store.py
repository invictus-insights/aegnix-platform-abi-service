# reflection/store.py

from abc import ABC, abstractmethod
from reflection.models import ReflectionEvent


class ReflectionStore(ABC):

    @abstractmethod
    def append(self, event: ReflectionEvent) -> None:
        """
        Persist a reflection event.
        Append-only semantics.
        """
        raise NotImplementedError


class InMemoryReflectionStore(ReflectionStore):
    def __init__(self):
        self._events: list[ReflectionEvent] = []

    def append(self, event: ReflectionEvent) -> None:
        self._events.append(event)

    def all(self) -> list[ReflectionEvent]:
        return list(self._events)
