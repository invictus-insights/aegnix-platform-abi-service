# runtime_registry.py
"""

needs updating
"""

import time
from threading import Lock
from typing import Optional, Dict, Any, Callable

TransitionHook = Callable[[Dict[str, Any]], None]

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

        self.live: Dict[str, Dict[str, Any]] = {}
        self.stale: Dict[str, Dict[str, Any]] = {}
        self.dead: Dict[str, Dict[str, Any]] = {}

        self._lock = Lock()
        self._transition_hook: TransitionHook | None = None

    # def touch(self, ae_id: str, session_id: str | None = None):
    #     now = time.time()
    #     with self._lock:
    #         self.live[ae_id] = {
    #             "last_seen": now,
    #             "session_id": session_id,
    #         }
    #         self.stale.pop(ae_id, None)
    #         self.dead.pop(ae_id, None)

    # ------------------------------------------
    # Hook wiring (ABIState will set this)
    # ------------------------------------------
    def set_transition_hook(self, hook: TransitionHook | None):
        self._transition_hook = hook

    def _emit_transition(self, *, ae_id: str, from_state: str, to_state: str, rec: Dict[str, Any], reason: str):
        if not self._transition_hook:
            return

        payload = {
            "event": "runtime_transition",
            "ts": time.time(),
            "ae_id": ae_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,

            # record fields (best-effort)
            "first_seen": rec.get("first_seen"),
            "last_seen": rec.get("last_seen"),
            "session_id": rec.get("session_id"),

            "last_source": rec.get("last_source"),
            "last_intent": rec.get("last_intent"),
            "last_subject": rec.get("last_subject"),
            "quality": rec.get("quality"),

            "heartbeat_count": rec.get("heartbeat_count", 0),
            "meta": rec.get("meta"),
        }
        self._transition_hook(payload)

    def heartbeat(
            self,
            ae_id: str,
            session_id: Optional[str],
            *,
            source: str = "unknown",
            intent: str | None = None,
            subject: str | None = None,
            quality: str = "normal",
            meta: dict | None = None,
    ):
        now = time.time()
        with self._lock:
            prev_state = None
            rec = self.live.get(ae_id)
            if rec is not None:
                prev_state = "live"
            else:
                rec = self.stale.get(ae_id)
                if rec is not None:
                    prev_state = "stale"
                else:
                    rec = self.dead.get(ae_id)
                    if rec is not None:
                        prev_state = "dead"
                    else:
                        rec = {}
                        prev_state = "none"

            rec.update({
                "first_seen": rec.get("first_seen", now),
                "last_seen": now,
                "session_id": session_id,

                # semantic fields
                "last_source": source,
                "last_intent": intent,
                "last_subject": subject,
                "quality": quality,

                # counters / metadata
                "heartbeat_count": int(rec.get("heartbeat_count", 0)) + 1,
                "meta": meta,
            })

            self.live[ae_id] = rec
            self.stale.pop(ae_id, None)
            self.dead.pop(ae_id, None)

            # Emit outside lock
            if prev_state != "live":
                self._emit_transition(
                    ae_id=ae_id,
                    from_state=prev_state,
                    to_state="live",
                    rec=rec,
                    reason="heartbeat",
                )

    def sweep(self):
        now = time.time()

        stale_moves: list[tuple[str, Dict[str, Any], str, str, str]] = []
        dead_moves: list[tuple[str, Dict[str, Any], str, str, str]] = []

        with self._lock:
            # live -> stale/dead
            for ae_id, rec in list(self.live.items()):
                age = now - rec["last_seen"]
                if age >= self.dead_after:
                    self.dead[ae_id] = rec
                    self.live.pop(ae_id)
                    dead_moves.append((ae_id, rec, "live", "dead", "sweep_dead"))
                elif age >= self.stale_after:
                    self.stale[ae_id] = rec
                    self.live.pop(ae_id)
                    stale_moves.append((ae_id, rec, "live", "stale", "sweep_stale"))

            # stale -> dead
            for ae_id, rec in list(self.stale.items()):
                age = now - rec["last_seen"]
                if age >= self.dead_after:
                    self.dead[ae_id] = rec
                    self.stale.pop(ae_id)
                    dead_moves.append((ae_id, rec, "stale", "dead", "sweep_dead"))

        # emit outside lock
        for ae_id, rec, f, t, reason in stale_moves:
            self._emit_transition(ae_id=ae_id, from_state=f, to_state=t, rec=rec, reason=reason)
        for ae_id, rec, f, t, reason in dead_moves:
            self._emit_transition(ae_id=ae_id, from_state=f, to_state=t, rec=rec, reason=reason)

# Global singleton (imported in main.py and routes)
runtime_registry = RuntimeRegistry()
