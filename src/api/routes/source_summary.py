from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from src.api.run_status import get_run

router = APIRouter(prefix="/api/v1/pipelines/review", tags=["pipelines"])


@router.get("/runs/{run_id}/source")
def get_pipeline_run_source(run_id: str) -> dict[str, Optional[str]]:
    """Return the source summary for a pipeline run."""
    run = get_run(run_id)
    if run is None:
        return {"source_url": None, "resolved_source_url": None, "source_content_type": None, "source_format": None, "source_artifact_path": None, "source_status": None}

    return {
        "source_url": run.source_url,
        "resolved_source_url": run.resolved_source_url,
        "source_content_type": run.source_content_type,
        "source_format": run.source_format,
        "source_artifact_path": run.source_artifact_path,
        "source_status": run.source_status,
    }
