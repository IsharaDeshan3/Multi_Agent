from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from fastapi import APIRouter, HTTPException

from src.agents.parser_agent import parser_node
from src.api.schemas import (
    AgentExecuteRequest,
    AgentListEnvelope,
    AgentMetadataResponse,
    ReviewStateEnvelope,
)
from src.state import ReviewStateModel, validate_review_state

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


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


@router.get("", response_model=AgentListEnvelope)
def get_agents() -> AgentListEnvelope:
    """List the currently implemented parser agent."""
    agents = [
        AgentMetadataResponse(
            name="parser",
            stage="parser",
            version="0.1.0",
            description="Leader parser agent.",
            ready="True",
        )
    ]
    return AgentListEnvelope(agents=agents)


@router.post("/{agent_name}/execute", response_model=ReviewStateEnvelope)
def execute_single_agent(
    agent_name: str,
    payload: AgentExecuteRequest,
) -> ReviewStateEnvelope:
    """Execute the parser agent against submitted ReviewState."""
    if agent_name != "parser":
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")

    input_state = validate_review_state(payload.state.model_dump())

    try:
        with _temporary_parser_input_path(payload.parser_input_path):
            updated_state = parser_node(input_state)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    validated = ReviewStateModel.model_validate(updated_state)
    return ReviewStateEnvelope(state=validated)
