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

        # NEW — Track AE liveness (emit, subscribe, heartbeat)
        self.runtime_registry = RuntimeRegistry()

    # ----------------------------------------------------------
    # Runtime Convenience
    # ----------------------------------------------------------
    def touch(self, ae_id: str, session_id: str):
        """Record a heartbeat/liveness touch event."""
        self.runtime_registry.touch(ae_id, session_id)

    def get_live_agents(self):
        return self.runtime_registry.get_live_aes()

    def get_stale_agents(self):
        return self.runtime_registry.get_stale_aes()

    def get_agent_state(self, ae_id: str):
        return self.runtime_registry.get(ae_id)

