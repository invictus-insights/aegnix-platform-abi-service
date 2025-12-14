# reflection/query.py

from typing import List, Optional
from reflection.models import ReflectionRecord
from reflection.store import ReflectionStore
from reflection.timeline import build_session_timeline


def get_records(
    store: ReflectionStore,
    *,
    ae_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 500,
) -> List[ReflectionRecord]:
    """
    Deterministic read of reflection records with optional filters.
    """

    records: List[ReflectionRecord] = []

    for r in store.all():
        if ae_id and r.correlation.ae_id != ae_id:
            continue
        if session_id and r.correlation.session_id != session_id:
            continue
        if event_type and r.event_type != event_type:
            continue
        if since is not None and r.ts < since:
            continue
        if until is not None and r.ts > until:
            continue

        records.append(r)

    records.sort(key=lambda r: r.ts)
    return records[:limit]


def get_session_timeline(
    store: ReflectionStore,
    ae_id: str,
    session_id: str,
) -> dict:
    """
    Retrieve a deterministic timeline for an AE session.
    """
    return build_session_timeline(store, ae_id, session_id)


def get_sessions_for_ae(
    store: ReflectionStore,
    ae_id: str,
) -> List[str]:
    """
    Return sorted session IDs observed for an AE.
    """
    sessions = set()

    for r in store.all():
        if r.correlation.ae_id == ae_id and r.correlation.session_id:
            sessions.add(r.correlation.session_id)

    return sorted(sessions)


def what_happened(
    store: ReflectionStore,
    ae_id: str,
    session_id: str,
) -> dict:
    """
    Return the raw factual record of what occurred during a session.
    """
    timeline = get_session_timeline(store, ae_id, session_id)

    return {
        "ae_id": ae_id,
        "session_id": session_id,
        "start_ts": timeline["start_ts"],
        "end_ts": timeline["end_ts"],
        "records": timeline["records"],
        "transitions": timeline["transitions"],
    }


def why_did_it_stop(
    store: ReflectionStore,
    ae_id: str,
    session_id: str,
) -> dict:
    """
    Return the last known state and events for a session.
    """
    timeline = get_session_timeline(store, ae_id, session_id)
    records = timeline["records"]

    if not records:
        return {
            "status": "no-data",
            "ae_id": ae_id,
            "session_id": session_id,
        }

    last_record = records[-1]

    return {
        "status": "ended-without-explicit-close",
        "ae_id": ae_id,
        "session_id": session_id,
        "last_ts": last_record.ts,
        "last_event_type": last_record.event_type,
        "last_intent": last_record.intent,
        "last_transitions": last_record.transitions,
        "last_record": last_record,
    }


def what_preceded_failure(
    store: ReflectionStore,
    ae_id: str,
    session_id: str,
    window: int = 5,
) -> dict:
    """
    Return the raw events preceding a failure transition.
    """
    timeline = get_session_timeline(store, ae_id, session_id)
    records = timeline["records"]

    for idx, r in enumerate(records):
        for t in r.transitions:
            if t.name == "error":
                start = max(0, idx - window)
                return {
                    "status": "failure-detected",
                    "ae_id": ae_id,
                    "session_id": session_id,
                    "failure_ts": t.ts,
                    "failure_transition": t,
                    "preceding_records": records[start:idx],
                }

    return {
        "status": "no-failure-detected",
        "ae_id": ae_id,
        "session_id": session_id,
    }


