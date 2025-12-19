from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional

from reflection.store import ReflectionStore
from reflection.query import (
    get_records,
    get_session_timeline,
    get_sessions_for_ae,
    what_happened,
    why_did_it_stop,
    what_preceded_failure,
    get_sessions_for_ae_by_recency,
)

from aegnix_core.storage import load_storage_provider
from reflection.sqlite_store import SQLiteReflectionStore


def reflection_store() -> ReflectionStore:
    return SQLiteReflectionStore(load_storage_provider())


router = APIRouter()


@router.get("/aes")
def list_aes(store: ReflectionStore = Depends(reflection_store)):
    """
    List all AE IDs observed in reflection records.

    Operator-only visibility.
    No mutation.
    """
    ae_ids = set()

    for r in store.all():
        if r.correlation.ae_id:
            ae_ids.add(r.correlation.ae_id)

    return {"aes": sorted(ae_ids), "count": len(ae_ids)}


@router.get("/aes/{ae_id}/sessions")
def list_sessions_for_ae(ae_id: str, store: ReflectionStore = Depends(reflection_store)):
    """
    List session IDs observed for a given AE.
    """
    sessions = get_sessions_for_ae(store, ae_id)

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found for AE")

    return {
        "ae_id": ae_id,
        "count": len(sessions),
        "sessions": sessions,
    }


@router.get("/aes/{ae_id}/sessions/recent")
def list_sessions_for_ae_recent(
    ae_id: str,
    store: ReflectionStore = Depends(reflection_store),
):
    """
    List sessions for an AE ordered by most recent activity.
    """
    sessions = get_sessions_for_ae_by_recency(store, ae_id)

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found for AE")

    return {
        "ae_id": ae_id,
        "count": len(sessions),
        "sessions": sessions,
    }


@router.get("/aes/{ae_id}/sessions/{session_id}/timeline")
def get_timeline(ae_id: str, session_id: str, store: ReflectionStore = Depends(reflection_store)):
    """
    Retrieve the full deterministic timeline for an AE session.
    """
    timeline = get_session_timeline(store, ae_id, session_id)

    if not timeline["records"]:
        raise HTTPException(status_code=404, detail="Session not found")

    return timeline


@router.get("/aes/{ae_id}/sessions/{session_id}/what-happened")
def operator_what_happened(ae_id: str, session_id: str, store: ReflectionStore = Depends(reflection_store)):
    """
    Operator-facing factual session summary.
    """
    return what_happened(store, ae_id, session_id)


@router.get("/aes/{ae_id}/sessions/{session_id}/why-stopped")
def operator_why_stopped(ae_id: str, session_id: str, store: ReflectionStore = Depends(reflection_store)):
    """
    Explain the last observed state of a session without inference.
    """
    return why_did_it_stop(store, ae_id, session_id)


@router.get("/aes/{ae_id}/sessions/{session_id}/preceded-failure")
def operator_preceded_failure(
    ae_id: str,
    session_id: str,
    window: int = Query(default=5, ge=1, le=50),
    store: ReflectionStore = Depends(reflection_store)
):
    """
    Retrieve events leading up to a detected failure.
    """
    return what_preceded_failure(store, ae_id, session_id, window=window)


@router.get("/records")
def query_records(
    ae_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    store: ReflectionStore = Depends(reflection_store)
):
    """
    Low-level reflection record query.

    Intended for advanced operators and debugging tools.
    """
    records = get_records(
        store,
        ae_id=ae_id,
        session_id=session_id,
        event_type=event_type,
        limit=limit,
    )

    return {
        "count": len(records),
        "records": records,
    }
