# abi_state.py — Phase 4 Runtime ABI State Container

from runtime_registry import RuntimeRegistry
import time
import logging

log = logging.getLogger("ABI.Runtime")


class ABIState:
    """
    Central ABI state container for Phase-4.

    Holds:
      - SessionManager
      - Keyring
      - Bus
      - Policy
      - RuntimeRegistry (AE liveness)

    Routes will receive this via injection from main.py.
    """

    def __init__(self, keyring, session_manager, bus, policy):
        self.keyring = keyring
        self.session_manager = session_manager
        self.bus = bus
        self.policy = policy
        self.runtime_registry = RuntimeRegistry()

        # Runtime transitions -> bus
        self.runtime_registry.set_transition_hook(self._on_runtime_transition)

    def _on_runtime_transition(self, evt: dict):
        """
        Runtime lifecycle events.
        Phase-4: publish to bus (local/in-memory bus for now).
        """
        if not self.bus:
            return

        topic = "abi.runtime.transition"

        try:
            if hasattr(self.bus, "publish"):
                self.bus.publish(topic, evt)
            elif hasattr(self.bus, "emit"):
                self.bus.emit(topic, evt)
        except RuntimeError as e:
            # Transport temporarily unavailable
            # (safe to drop telemetry)
            pass

    # ----------------------------------------------------------
    # Runtime Convenience
    # ----------------------------------------------------------
    def heartbeat(
            self,
            ae_id: str,
            session_id: str | None,
            source: str,
            *,
            intent: str | None = None,
            subject: str | None = None,
            quality: str = "normal",
            meta: dict | None = None,
    ):
        # Update runtime state (authoritative)
        self.runtime_registry.heartbeat(
            ae_id=ae_id,
            session_id=session_id,
            source=source,
            intent=intent,
            subject=subject,
            quality=quality,
            meta=meta,
        )

        # Emit runtime heartbeat event (best-effort)
        self._emit_runtime_event({
            "type": "heartbeat",
            "ae_id": ae_id,
            "session_id": session_id,
            "source": source,
            "intent": intent,
            "subject": subject,
            "quality": quality,
            "meta": meta,
            "ts": time.time(),
        })

    def get_live_agents(self):
        return self.runtime_registry.live

    def get_stale_agents(self):
        return self.runtime_registry.stale

    def get_dead_agents(self):
        return self.runtime_registry.dead

    def get_agent_state(self, ae_id: str):
        if ae_id in self.runtime_registry.live:
            return self.runtime_registry.live[ae_id]
        if ae_id in self.runtime_registry.stale:
            return self.runtime_registry.stale[ae_id]
        if ae_id in self.runtime_registry.dead:
            return self.runtime_registry.dead[ae_id]
        return None

    @staticmethod
    def normalize_runtime_record(rec: dict, ae_id: str | None = None) -> dict:
    # def normalize_runtime_record(rec: dict | None):
        if not rec:
            return None

        return {
            "ae_id": ae_id,
            # "ae_id": rec.get("ae_id"),
            "session_id": rec.get("session_id"),

            "state": rec.get("state", "unknown"),
            "first_seen": rec.get("first_seen"),
            "last_seen": rec.get("last_seen"),

            "last_source": rec.get("last_source"),
            "last_intent": rec.get("last_intent"),
            "last_subject": rec.get("last_subject"),
            "quality": rec.get("quality", "normal"),

            "heartbeat_count": rec.get("heartbeat_count", 0),
            "meta": rec.get("meta"),
        }

    # ----------------------------------------------------------
    # Runtime → Event Hook (Phase 4.4)
    # ----------------------------------------------------------
    """
    Runtime Event Contract (Phase 4+)
    Events emitted on topic: `ae.runtime`

    Base fields:
    - type: str
    - ae_id: str
    - ts: float (epoch seconds)

    Optional fields:
    - session_id
    - source
    - intent
    - subject
    - quality
    - meta
    - from_state
    - to_state
    """

    def _emit_runtime_event(self, event: dict):
        """
        Best-effort runtime event emission.

        This is a hook point only.
        - No guarantees
        - No persistence
        - No blocking
        """
        try:
            if not self.bus:
                return

            if not hasattr(self.bus, "publish"):
                return

            # Topic is intentionally generic for now
            self.bus.publish("ae.runtime", event)

        except Exception as e:
            # Runtime observability must never break control flow
            log.warning({
                "event": "runtime_event_emit_failed",
                "error": str(e),
                "payload_type": event.get("type"),
            })



