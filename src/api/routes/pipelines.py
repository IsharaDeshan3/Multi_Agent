from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from fastapi import APIRouter, HTTPException

from src.api.schemas import PipelineExecuteRequest, ReviewStateEnvelope
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
