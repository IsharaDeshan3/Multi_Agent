from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class RunStatus:
    """In-memory status record for a pipeline run."""

    run_id: str
    status: str
    current_stage: str
    stage_index: int
    stage_total: int
    started_at: str
    updated_at: str
    messages: List[str] = field(default_factory=list)
    error: Optional[str] = None
    result_state: Optional[Dict[str, Any]] = None
    source_url: Optional[str] = None
    resolved_source_url: Optional[str] = None
    source_content_type: Optional[str] = None
    source_artifact_path: Optional[str] = None
    source_status: Optional[str] = None


_RUN_STORE: Dict[str, RunStatus] = {}
_RUN_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run(stage_total: int, source_url: Optional[str] = None) -> RunStatus:
    """Create a new run record and return it."""
    run_id = str(uuid4())
    now = _now_iso()
    status = RunStatus(
        run_id=run_id,
        status="queued",
        current_stage="pending",
        stage_index=0,
        stage_total=stage_total,
        started_at=now,
        updated_at=now,
        messages=["Run queued."],
        source_url=source_url,
        source_status="pending" if source_url else None,
    )
    with _RUN_LOCK:
        _RUN_STORE[run_id] = status
    return status


def get_run(run_id: str) -> Optional[RunStatus]:
    """Fetch a run record by id."""
    with _RUN_LOCK:
        return _RUN_STORE.get(run_id)


def update_run(run_id: str, **updates: Any) -> Optional[RunStatus]:
    """Update a run record in-place and return it."""
    with _RUN_LOCK:
        status = _RUN_STORE.get(run_id)
        if status is None:
            return None

        for key, value in updates.items():
            if hasattr(status, key):
                setattr(status, key, value)
        status.updated_at = _now_iso()
        _RUN_STORE[run_id] = status
        return status


def append_message(run_id: str, message: str) -> Optional[RunStatus]:
    """Append a message to the run log."""
    with _RUN_LOCK:
        status = _RUN_STORE.get(run_id)
        if status is None:
            return None
        status.messages.append(message)
        status.updated_at = _now_iso()
        _RUN_STORE[run_id] = status
        return status


def run_to_dict(status: RunStatus) -> Dict[str, Any]:
    """Convert a run record into a JSON-serializable dict."""
    return {
        "run_id": status.run_id,
        "status": status.status,
        "current_stage": status.current_stage,
        "stage_index": status.stage_index,
        "stage_total": status.stage_total,
        "started_at": status.started_at,
        "updated_at": status.updated_at,
        "messages": list(status.messages),
        "error": status.error,
        "result_state": status.result_state,
        "source_url": status.source_url,
        "resolved_source_url": status.resolved_source_url,
        "source_content_type": status.source_content_type,
        "source_artifact_path": status.source_artifact_path,
        "source_status": status.source_status,
    }
