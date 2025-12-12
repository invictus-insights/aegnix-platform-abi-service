# runtime_registry.py
"""
Runtime Registry for AE Liveness Tracking (Layer-4 Step-4)

This registry tracks:
  - Last time each AE was seen
  - Whether the ABI considers an AE "online" or "stale"
  - Optional metadata (session_id, last capability declaration, etc.)

Patch-1: Minimal functional registry
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum

# Consider AE stale if no activity for more than this duration
STALE_THRESHOLD = timedelta(minutes=5)
STALE_AFTER = timedelta(seconds=15)
DEAD_AFTER = timedelta(seconds=60)

class AELifecycle(str, Enum):
    LIVE = "live"
    STALE = "stale"
    DEAD = "dead"


@dataclass
class AERuntimeState:
    ae_id: str
    last_seen: datetime
    session_id: Optional[str] = None
    last_capability_declared: Optional[datetime] = None
    lifecycle: AELifecycle = AELifecycle.LIVE

    # def is_stale(self) -> bool:
    #     return datetime.utcnow() - self.last_seen > STALE_THRESHOLD

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["lifecycle"] = self.lifecycle.value
        # d["is_stale"] = self.is_stale()
        d["last_seen"] = self.last_seen.isoformat()
        if self.last_capability_declared:
            d["last_capability_declared"] = self.last_capability_declared.isoformat()
        return d


class RuntimeRegistry:
    """
    In-memory process-local registry of active AEs.

    Lifecycle:
      - ABI receives /verify → AE is alive
      - ABI receives /ae/capabilities → AE is alive
      - ABI receives /emit → AE is alive
      - /admin/runtime/agents (coming in Patch-3) will expose this registry

    Patch-1 does NOT wire registry into routes yet.
    """

    def __init__(self):
        self._agents: Dict[str, AERuntimeState] = {}

    def touch(self, ae_id: str, session_id: Optional[str] = None):
        """
        Mark an AE as seen. Creates if not present.
        """
        now = datetime.utcnow()

        if ae_id not in self._agents:
            self._agents[ae_id] = AERuntimeState(
                ae_id=ae_id,
                last_seen=now,
                session_id=session_id,
            )
        else:
            state = self._agents[ae_id]
            state.last_seen = now
            state.lifecycle = AELifecycle.LIVE
            if session_id:
                state.session_id = session_id

    def sweep(self):
        """
        Phase 4B Step-1:
        Background lifecycle transitions.
        """
        now = datetime.utcnow()
        newly_stale = []
        newly_dead = []

        for ae_id, state in self._agents.items():

            # LIVE → STALE
            if state.lifecycle == AELifecycle.LIVE:
                if now - state.last_seen > STALE_AFTER:
                    state.lifecycle = AELifecycle.STALE
                    newly_stale.append(ae_id)

            # STALE → DEAD
            elif state.lifecycle == AELifecycle.STALE:
                if now - state.last_seen > DEAD_AFTER:
                    state.lifecycle = AELifecycle.DEAD
                    newly_dead.append(ae_id)

        return newly_stale, newly_dead


    def update_capability_timestamp(self, ae_id: str):
        """
        Called when AE declares or re-declares capabilities.
        """
        now = datetime.utcnow()
        if ae_id in self._agents:
            self._agents[ae_id].last_capability_declared = now
        else:
            # If not tracked yet, create and set both timestamps
            self._agents[ae_id] = AERuntimeState(
                ae_id=ae_id,
                last_seen=now,
                last_capability_declared=now,
            )

    def get_all(self) -> Dict[str, Dict]:
        """
        Returns a dict mapping ae_id → runtime info dict(), all serializable.
        """
        return {ae_id: state.to_dict() for ae_id, state in self._agents.items()}

    def get(self, ae_id: str) -> Optional[Dict]:
        """
        Returns dict form of the runtime state for one AE.
        """
        if ae_id not in self._agents:
            return None
        return self._agents[ae_id].to_dict()

    # ----------------------------------------------------------
    # Live / Stale Queries (Step-4 Patch-3)
    # ----------------------------------------------------------
    def get_live_aes(self):
        """
        Returns all NON-stale agents (recently active).
        """
        return {
            ae_id: state.to_dict()
            for ae_id, state in self._agents.items()
            # if not state.is_stale()
            if state.lifecycle == AELifecycle.LIVE
        }

    def get_stale_aes(self):
        """
        Returns all agents whose last_seen exceeded STALE_THRESHOLD.
        """
        return {
            ae_id: state.to_dict()
            for ae_id, state in self._agents.items()
            # if state.is_stale()
            if state.lifecycle == AELifecycle.STALE
        }

    def get_dead_aes(self):
        return {
            ae_id: state.to_dict()
            for ae_id, state in self._agents.items()
            if state.lifecycle == AELifecycle.DEAD
        }


# Global singleton (imported in main.py and routes)
runtime_registry = RuntimeRegistry()
