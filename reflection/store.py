# reflection/store.py

from typing import List
from abc import ABC, abstractmethod
from reflection.models import ReflectionRecord


class ReflectionStore(ABC):

    @abstractmethod
    def append(self, record: ReflectionRecord) -> None:
        """
        Persist a reflection record.
        Append-only semantics.
        """
        raise NotImplementedError

    @abstractmethod
    def all(self) -> List[ReflectionRecord]:
        """
        Return all reflection records.
        Read-only view.
        """
        raise NotImplementedError


class InMemoryReflectionStore(ReflectionStore):
    def __init__(self):
        self._events: list[ReflectionRecord] = []

    def append(self, event: ReflectionRecord) -> None:
        self._events.append(event)

    def all(self) -> list[ReflectionRecord]:
        return list(self._events)
