# reflection/timeline.py

from typing import List, Optional
from reflection.models import ReflectionRecord, Transition
from reflection.store import ReflectionStore


def _infer_end_status(transitions: List[Transition]) -> str:
    """
    Determine terminal session status from transitions.
    """
    for t in reversed(transitions):
        if t.name in ("dead", "error", "closed"):
            return t.name
    return "ended-without-explicit-close"


def get_sessions_for_ae(store: ReflectionStore, ae_id: str) -> List[str]:
    """
    Return all distinct session_ids observed for an AE.
    """
    sessions = set()

    for record in store.all():
        corr = record.correlation
        if corr.ae_id == ae_id and corr.session_id:
            sessions.add(corr.session_id)

    return sorted(sessions)


def build_session_timeline(
    store: ReflectionStore,
    ae_id: str,
    session_id: str,
) -> dict:
    """
    Build an ordered timeline of events for a given AE session.
    """

    records: List[ReflectionRecord] = [
        r for r in store.all()
        if r.correlation.ae_id == ae_id
        and r.correlation.session_id == session_id
    ]

    # Deterministic ordering
    records.sort(key=lambda r: r.ts)

    transitions: List[Transition] = []
    for r in records:
        transitions.extend(r.transitions)

    start_ts: Optional[float] = records[0].ts if records else None
    end_ts: Optional[float] = records[-1].ts if records else None

    end_status = _infer_end_status(transitions)

    return {
        "ae_id": ae_id,
        "session_id": session_id,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "end_status": end_status,
        "records": records,
        "transitions": transitions,
    }
