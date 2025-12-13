# reflection/models.py

from typing import Optional, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class ReflectionEvent:
    """
    Immutable semantic memory record.
    """
    event_type: str               # ae.runtime | abi.runtime.transition
    ae_id: str
    session_id: Optional[str]

    ts: float

    source: Optional[str] = None
    intent: Optional[str] = None
    subject: Optional[str] = None
    quality: Optional[str] = None

    from_state: Optional[str] = None
    to_state: Optional[str] = None

    meta: Dict[str, Any] | None = None
