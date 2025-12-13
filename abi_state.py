# abi_state.py — Phase 4 Runtime ABI State Container

from runtime_registry import RuntimeRegistry


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
        # self.runtime_registry.touch(
        self.runtime_registry.heartbeat(

            ae_id=ae_id,
            session_id=session_id,
            source=source,
            intent=intent,
            subject=subject,
            quality=quality,
            meta=meta,
        )

    # def heartbeat(self, ae_id: str, session_id: str | None, source: str):
    #     """
    #     Semantic liveness signal.
    #
    #     source = emit | subscribe | register | explicit
    #     """
    #     # self.runtime_registry.touch(ae_id, session_id)
    #     self.runtime_registry.heartbeat(ae_id, session_id, source=source)
    #
    #     # Phase-5+ hooks:
    #     # - metrics
    #     # - policy
    #     # - anomaly detection
    #     # - audit correlation
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



