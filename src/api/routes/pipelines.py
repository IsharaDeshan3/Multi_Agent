from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.api.run_status import append_message, create_run, get_run, run_to_dict, update_run
from src.api.schemas import PipelineExecuteRequest, ReviewStateEnvelope, RunStatusResponse
from src.state import ReviewStateModel, create_initial_state, validate_review_state
from src.workflow.main import resume_from_stage, run_full_pipeline, run_until_stage

router = APIRouter(prefix="/api/v1/pipelines/review", tags=["pipelines"])


@contextmanager
def _temporary_parser_input_path(parser_input_path: Optional[str]) -> Iterator[None]:
    """Temporarily override parser input path for request-scoped execution."""
    if not parser_input_path:
        yield
        return

    previous = os.getenv("PARSER_INPUT_PATH")
    os.environ["PARSER_INPUT_PATH"] = parser_input_path

    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PARSER_INPUT_PATH", None)
        else:
            os.environ["PARSER_INPUT_PATH"] = previous


def _resolve_state(payload: PipelineExecuteRequest):
    """Resolve optional request state into a validated ReviewState dict."""
    if payload.state is None:
        return create_initial_state()
    return validate_review_state(payload.state.model_dump())


def _run_pipeline_background(run_id: str, payload: PipelineExecuteRequest) -> None:
    input_state = _resolve_state(payload)

    update_run(
        run_id,
        status="running",
        current_stage="parser",
        stage_index=1,
    )
    append_message(run_id, "Stage parser started.")

    try:
        with _temporary_parser_input_path(payload.parser_input_path):
            result = run_full_pipeline(input_state)
    except Exception as exc:
        update_run(
            run_id,
            status="failed",
            error=str(exc),
        )
        append_message(run_id, f"Run failed: {exc}")
        return

    update_run(
        run_id,
        status="completed",
        current_stage="parser",
        stage_index=1,
        result_state=ReviewStateModel.model_validate(result).model_dump(),
    )
    append_message(run_id, "Run completed.")


@router.post("/execute", response_model=ReviewStateEnvelope)
def execute_pipeline(payload: PipelineExecuteRequest) -> ReviewStateEnvelope:
    """Run the parser-only pipeline."""
    input_state = _resolve_state(payload)

    try:
        with _temporary_parser_input_path(payload.parser_input_path):
            result = run_full_pipeline(input_state)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReviewStateEnvelope(state=ReviewStateModel.model_validate(result))


@router.post("/runs", response_model=RunStatusResponse)
def start_pipeline_run(
    payload: PipelineExecuteRequest,
    background_tasks: BackgroundTasks,
) -> RunStatusResponse:
    """Start a background pipeline run and return its run status."""
    run = create_run(stage_total=1)
    background_tasks.add_task(_run_pipeline_background, run.run_id, payload)
    return RunStatusResponse(**run_to_dict(run))


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_pipeline_run_status(run_id: str) -> RunStatusResponse:
    """Fetch the status of a pipeline run."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run id: {run_id}")
    return RunStatusResponse(**run_to_dict(run))


@router.post("/execute-until/{stage}", response_model=ReviewStateEnvelope)
def execute_pipeline_until_stage(
    stage: str,
    payload: PipelineExecuteRequest,
) -> ReviewStateEnvelope:
    """Run the parser stage when the requested stage is parser."""
    input_state = _resolve_state(payload)

    try:
        with _temporary_parser_input_path(payload.parser_input_path):
            result = run_until_stage(stage=stage, state=input_state)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReviewStateEnvelope(state=ReviewStateModel.model_validate(result))


@router.post("/resume-from/{stage}", response_model=ReviewStateEnvelope)
def resume_pipeline_from_stage(
    stage: str,
    payload: PipelineExecuteRequest,
) -> ReviewStateEnvelope:
    """Resume the parser stage when the provided stage is parser."""
    if payload.state is None:
        raise HTTPException(status_code=422, detail="state is required to resume from a stage")

    input_state = validate_review_state(payload.state.model_dump())

    try:
        with _temporary_parser_input_path(payload.parser_input_path):
            result = resume_from_stage(stage=stage, state=input_state)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReviewStateEnvelope(state=ReviewStateModel.model_validate(result))
