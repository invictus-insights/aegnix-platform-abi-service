# reflection/models.py

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
import time
import uuid
import  json


@dataclass(frozen=True)
class Transition:
    """
    Explicit state transition extracted from runtime/control events.
    """
    name: str                    # e.g. lifecycle, capability, error
    from_state: Optional[str]
    to_state: Optional[str]
    reason: Optional[str]
    ts: float


@dataclass(frozen=True)
class Correlation:
    """
    Deterministic linkage metadata.
    """
    ae_id: Optional[str]
    session_id: Optional[str]
    trace_id: Optional[str] = None
    confidence: str = "high"     # high | medium | low


@dataclass(frozen=True)
class ReflectionRecord:
    """
    Canonical, append-only reflection record.
    This is the durable semantic truth of the system.
    """

    # Identity
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = field(default_factory=lambda: time.time())

    # Classification
    domain: str = "runtime"      # runtime | abi | ae | transport
    event_type: str = ""         # ae.runtime.heartbeat, abi.runtime.transition

    # Semantics
    intent: Optional[str] = None
    subject: Optional[Dict[str, Any]] = None

    # Source
    source: Optional[Dict[str, Any]] = None   # emitter identity

    # Correlation
    correlation: Correlation = field(
        default_factory=lambda: Correlation(ae_id=None, session_id=None, confidence="low")
    )

    # State
    transitions: List[Transition] = field(default_factory=list)

    # Severity & quality
    severity: str = "info"       # info | warn | error
    quality: Optional[str] = None

    # Raw payload (bounded)
    payload: Dict[str, Any] = field(default_factory=dict)

    # Lightweight indexing / filtering
    labels: Dict[str, str] = field(default_factory=dict)


def serialize_record(record: ReflectionRecord) -> str:
    """
    Serialize a ReflectionRecord to JSON for durable storage.
    Explicit, deterministic, no inference.
    """
    return json.dumps(asdict(record), default=str)


def deserialize_record(payload: str) -> ReflectionRecord:
    """
    Rehydrate a ReflectionRecord from stored JSON.
    """
    data = json.loads(payload)

    return ReflectionRecord(
        **data,
        correlation=Correlation(**data["correlation"]),
        transitions=[
            Transition(**t) for t in data.get("transitions", [])
        ],
    )