# sessions.py — Phase 4A: Continuous Trust / Session + Refresh Tokens

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from aegnix_core.logger import get_logger


log = get_logger("ABI.Session")


# ==============================================================================
#  Data Models
# ==============================================================================

@dataclass
class Session:
    id: str
    subject: str
    pubkey_fpr: str
    created_at: int
    expires_at: int
    last_seen_at: int
    status: str              # ACTIVE | STALE | REVOKED | EXPIRED
    max_idle_sec: int
    metadata: Dict[str, Any]


@dataclass
class RefreshToken:
    id: str
    session_id: str
    token_hash: str
    created_at: int
    expires_at: int
    revoked: int
    rotation: int
    reason: Optional[str]


# ==============================================================================
#  SessionManager — primary interface
# ==============================================================================

class SessionManager:
    """
    Handles creation, lookup, refresh rotation, idle timeout, and revocation
    for AE sessions. Uses SQLiteStorage for persistence.
    """

    def __init__(self, store):
        self.store = store
        self._ensure_tables()


        # Default profiles (extend or load from YAML later posr phase 4 )
        self.profiles = {

            # Universal test + baseline AE profile
            "default": {
                "session_lifetime_sec": 24 * 3600,
                "refresh_lifetime_sec": 24 * 3600,
                "access_ttl_sec": 300,
                "max_idle_sec": 600,
            },

            "tactical_ae": {
                "session_lifetime_sec": 24 * 3600,
                "refresh_lifetime_sec": 24 * 3600,
                "access_ttl_sec": 300,
                "max_idle_sec": 600,
            },
            "backend_daemon": {
                "session_lifetime_sec": 30 * 24 * 3600,
                "refresh_lifetime_sec": 7 * 24 * 3600,
                "access_ttl_sec": 900,
                "max_idle_sec": 24 * 3600,
            },
        }

    # ==========================================================================
    #  Table Creation
    # ==========================================================================
    def _ensure_tables(self):
        """Create SQLite tables if they do not already exist."""
        self.store.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                pubkey_fpr TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL,
                status TEXT NOT NULL,
                max_idle_sec INTEGER NOT NULL,
                metadata TEXT
            );
        """)

        self.store.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL,
                rotation INTEGER NOT NULL,
                reason TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
        """)

        log.info("[ABI] Session tables ready.")

    # ==========================================================================
    #  Utility
    # ==========================================================================
    @staticmethod
    def _now() -> int:
        return int(time.time())

    @staticmethod
    def _hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf8")).hexdigest()

    # ==========================================================================
    #  Session Creation
    # ==========================================================================
    def create_session(self, subject: str, pubkey_fpr: str, profile: str = "tactical_ae",
                       metadata: Optional[Dict[str, Any]] = None) -> Session:
        """
        Create a new session for an AE based on its profile.
        """
        if profile not in self.profiles:
            raise ValueError(f"Unknown session profile: {profile}")

        p = self.profiles[profile]
        now = self._now()

        sid = str(uuid.uuid4())
        expires = now + p["session_lifetime_sec"]

        record = {
            "id": sid,
            "subject": subject,
            "pubkey_fpr": pubkey_fpr,
            "created_at": now,
            "expires_at": expires,
            "last_seen_at": now,
            "status": "ACTIVE",
            "max_idle_sec": p["max_idle_sec"],
            "metadata": json.dumps(metadata or {}),
        }

        self.store.insert("sessions", record)

        log.info(f"[ABI] Session created: sid={sid} subject={subject}")

        return self.get_session(sid)

    # ==========================================================================
    #  Refresh Token Creation
    # ==========================================================================
    def create_refresh_token(self, session_id: str, profile: str = "tactical_ae") -> (str, RefreshToken):
        """Create a new refresh token for a given session."""
        p = self.profiles[profile]
        now = self._now()

        raw = uuid.uuid4().hex + uuid.uuid4().hex  # 256 bits
        token_hash = self._hash_token(raw)

        rid = str(uuid.uuid4())
        record = {
            "id": rid,
            "session_id": session_id,
            "token_hash": token_hash,
            "created_at": now,
            "expires_at": now + p["refresh_lifetime_sec"],
            "revoked": 0,
            "rotation": 0,
            "reason": None,
        }

        self.store.insert("refresh_tokens", record)

        log.info(f"[ABI] Refresh token issued for sid={session_id}")

        return raw, self.get_refresh_token(rid)

    # ==========================================================================
    #  Lookup Helpers
    # ==========================================================================
    def get_session(self, sid: str) -> Optional[Session]:
        row = self.store.fetch_one("SELECT * FROM sessions WHERE id=?", (sid,))
        if not row:
            return None
        return Session(
            id=row["id"],
            subject=row["subject"],
            pubkey_fpr=row["pubkey_fpr"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            last_seen_at=row["last_seen_at"],
            status=row["status"],
            max_idle_sec=row["max_idle_sec"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def get_refresh_token(self, rid: str) -> Optional[RefreshToken]:
        row = self.store.fetch_one("SELECT * FROM refresh_tokens WHERE id=?", (rid,))
        if not row:
            return None
        return RefreshToken(
            id=row["id"],
            session_id=row["session_id"],
            token_hash=row["token_hash"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            revoked=row["revoked"],
            rotation=row["rotation"],
            reason=row["reason"],
        )

    # ==========================================================================
    #  Validation Helpers
    # ==========================================================================
    def validate_refresh_token(self, session_id: str, raw: str) -> Optional[RefreshToken]:
        """Return RefreshToken if valid, else None."""
        token_hash = self._hash_token(raw)
        row = self.store.fetch_one("""
            SELECT * FROM refresh_tokens 
            WHERE session_id=? AND token_hash=? AND revoked=0
        """, (session_id, token_hash))

        if not row:
            return None

        token = RefreshToken(
            id=row["id"],
            session_id=row["session_id"],
            token_hash=row["token_hash"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            revoked=row["revoked"],
            rotation=row["rotation"],
            reason=row["reason"],
        )

        now = self._now()
        if token.expires_at < now:
            self.revoke_refresh_token(token.id, reason="expired")
            log.warning(f"[ABI] Expired refresh token rejected for sid={session_id}")
            return None

        return token

    # ==========================================================================
    #  Session Gate — applied during emission
    # ==========================================================================
    def assert_session_active(self, sid: str):
        session = self.get_session(sid)
        if not session:
            raise ValueError("Invalid session: not found")

        now = self._now()

        if session.status in ("REVOKED", "EXPIRED"):
            raise ValueError(f"Session {sid} inactive: {session.status}")

        # Idle timeout
        if now - session.last_seen_at > session.max_idle_sec:
            self._expire_session(sid, reason="idle_timeout")
            raise ValueError("Session expired due to idle timeout")

        # Hard expiration
        if now > session.expires_at:
            self._expire_session(sid, reason="session_lifetime")
            raise ValueError("Session expired")

    def touch(self, sid: str):
        """Update last_seen_at."""
        now = self._now()
        self.store.execute("UPDATE sessions SET last_seen_at=? WHERE id=?", (now, sid,))

    # ==========================================================================
    #  Revocation / Expiration
    # ==========================================================================
    def revoke_session(self, sid: str, reason: str = "admin_revoke"):
        """Admin or system may revoke a session."""
        self.store.execute("UPDATE sessions SET status='REVOKED' WHERE id=?", (sid,))
        self.store.execute(
            "UPDATE refresh_tokens SET revoked=1, reason=? WHERE session_id=?",
            (reason, sid)
        )
        log.warning(f"[ABI] Session revoked: {sid} reason={reason}")

    def revoke_refresh_token(self, rid: str, reason: str = "rotation"):
        self.store.execute(
            "UPDATE refresh_tokens SET revoked=1, reason=? WHERE id=?",
            (reason, rid)
        )

    def _expire_session(self, sid: str, reason: str):
        self.store.execute(
            "UPDATE sessions SET status='EXPIRED' WHERE id=?",
            (sid,)
        )
        self.store.execute(
            "UPDATE refresh_tokens SET revoked=1, reason=? WHERE session_id=?",
            (reason, sid)
        )
        log.info(f"[ABI] Session expired: {sid} reason={reason}")

    # ==========================================================================
    #  Refresh Rotation
    # ==========================================================================
    def rotate_refresh_token(self, token: RefreshToken) -> (str, RefreshToken):
        """
        Invalidate the old token, create a new one with rotation count +1.
        """
        self.revoke_refresh_token(token.id, reason="rotation")

        new_raw = uuid.uuid4().hex + uuid.uuid4().hex
        new_hash = self._hash_token(new_raw)

        new_rid = str(uuid.uuid4())
        now = self._now()

        expires = now + token.expires_at - token.created_at  # same lifetime window

        record = {
            "id": new_rid,
            "session_id": token.session_id,
            "token_hash": new_hash,
            "created_at": now,
            "expires_at": expires,
            "revoked": 0,
            "rotation": token.rotation + 1,
            "reason": None,
        }

        self.store.insert("refresh_tokens", record)

        log.info(f"[ABI] Refresh token rotated for sid={token.session_id}")

        return new_raw, self.get_refresh_token(new_rid)
