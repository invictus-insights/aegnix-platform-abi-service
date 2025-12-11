from sessions import SessionManager
from aegnix_core.storage import StorageProvider

session_manager: SessionManager | None = None


def init_abi_state(store: StorageProvider):
    """
    Initialize global session manager with the shared storage provider.
    """
    global session_manager
    session_manager = SessionManager(store)
