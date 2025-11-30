from sessions import SessionManager
from aegnix_core.storage import SQLiteStorage

session_manager: SessionManager = None

def init_abi_state(store: SQLiteStorage):
    """
    Initialize global session manager with the shared SQLite store.
    """
    global session_manager
    session_manager = SessionManager(store)
