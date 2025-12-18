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
    Deterministically retrieve reflection records with optional filters.

    Guarantees:
    - Deterministic ordering by timestamp
    - Read-only, append-only semantics
    - No inference, aggregation, or interpretation
    - No policy or correctness evaluation

    Non-Guarantees:
    - Does not infer causality
    - Does not evaluate success or failure
    - Does not apply Swarm Purpose Policy (SPP)

    This is a factual data access primitive.
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
    Retrieve a deterministic, ordered timeline for a single AE session.

    Guarantees:
    - Stable ordering of records by timestamp
    - Complete inclusion of all observed session events
    - Explicit session start and end boundaries (best-known)

    Non-Guarantees:
    - No inference of intent or correctness
    - No policy alignment evaluation
    - No assumption of graceful termination

    This function constructs a factual session envelope suitable
    for higher-level operator or governance analysis.
    """
    return build_session_timeline(store, ae_id, session_id)


def get_sessions_for_ae(
    store: ReflectionStore,
    ae_id: str,
) -> List[str]:
    """
    Return all distinct session identifiers observed for an AE.

    Guarantees:
    - Deterministic ordering of session IDs
    - Based solely on observed correlation data

    Non-Guarantees:
    - Does not imply session validity or completeness
    - Does not infer session success or failure

    This function answers "what sessions existed", nothing more.
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
    Return the raw, deterministic factual record of a session.

    Guarantees:
    - Deterministic ordering
    - Complete inclusion of recorded events
    - No inference or interpretation
    - No policy or correctness evaluation

    Non-Guarantees:
    - Does not explain intent or causality
    - Does not assess correctness or alignment
    - Does not recommend action

    This function answers "what happened",
    not "why it happened" or "what should be done".
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
    Return the last observed state of a session and its final events.

    Guarantees:
    - Deterministic selection of the last recorded event
    - Accurate reporting of final observed transitions

    Non-Guarantees:
    - Does not assert intent or failure cause
    - Does not determine responsibility
    - Does not evaluate policy violations

    This function reports the terminal facts of a session,
    not an explanation or root-cause analysis.
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
    Return raw events immediately preceding a detected failure transition.

    Guarantees:
    - Deterministic window selection
    - Inclusion of only observed historical events
    - No mutation or reinterpretation of records

    Non-Guarantees:
    - Does not claim causality
    - Does not determine fault or misalignment
    - Does not evaluate policy or correctness

    This function provides factual context only.
    Interpretation is explicitly left to higher layers.
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


