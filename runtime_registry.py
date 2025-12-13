# runtime_registry.py
"""

needs updating
"""

import time
from threading import Lock
from typing import Optional, Dict, Any

class RuntimeRegistry:

    def __init__(self, stale_after: int = 30, dead_after: int = 120):
        """
        Runtime lifecycle tracker.

        Args:
            stale_after (int): seconds after last_seen to mark AE as stale
            dead_after (int): seconds after last_seen to mark AE as dead
        """
        if dead_after <= stale_after:
            raise ValueError("dead_after must be > stale_after")

        self.stale_after = stale_after
        self.dead_after = dead_after

        # self.live = {}
        # self.stale = {}
        # self.dead = {}
        self.live: Dict[str, Dict[str, Any]] = {}
        self.stale: Dict[str, Dict[str, Any]] = {}
        self.dead: Dict[str, Dict[str, Any]] = {}


        self._lock = Lock()

    def touch(self, ae_id: str, session_id: str | None = None):
        now = time.time()
        with self._lock:
            self.live[ae_id] = {
                "last_seen": now,
                "session_id": session_id,
            }
            self.stale.pop(ae_id, None)
            self.dead.pop(ae_id, None)

        # Public semantic API

    def heartbeat(self, ae_id: str, session_id: Optional[str], source: str = "unknown"):
        now = time.time()
        with self._lock:
            rec = self.live.get(ae_id) or self.stale.get(ae_id) or self.dead.get(ae_id) or {}
            rec.update({
                "last_seen": now,
                "session_id": session_id,
                "last_source": source,
                "heartbeat_count": int(rec.get("heartbeat_count", 0)) + 1,
                "first_seen": rec.get("first_seen", now),
            })
            self.live[ae_id] = rec
            self.stale.pop(ae_id, None)
            self.dead.pop(ae_id, None)

    def sweep(self):
        now = time.time()
        with self._lock:
            for ae_id, rec in list(self.live.items()):
                age = now - rec["last_seen"]
                if age >= self.dead_after:
                    self.dead[ae_id] = rec
                    self.live.pop(ae_id)
                elif age >= self.stale_after:
                    self.stale[ae_id] = rec
                    self.live.pop(ae_id)

            for ae_id, rec in list(self.stale.items()):
                age = now - rec["last_seen"]
                if age >= self.dead_after:
                    self.dead[ae_id] = rec
                    self.stale.pop(ae_id)

    # def heartbeat(self, ae_id: str, session_id: str | None = None, source: str = "unknown"):
    #     """
    #     Record an explicit heartbeat.
    #
    #     `source` is informational only (emit, subscribe, register, etc.)
    #     """
    #     self.touch(ae_id, session_id)

# Global singleton (imported in main.py and routes)
runtime_registry = RuntimeRegistry()
