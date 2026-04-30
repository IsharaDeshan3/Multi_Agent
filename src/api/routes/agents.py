from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from fastapi import APIRouter, HTTPException

from src.agents.auditor_agent import auditor_node
from src.agents.critic_agent import critic_node
from src.agents.integrator_agent import integrator_node
from src.agents.parser_agent import parser_node
from src.api.schemas import (
    AgentExecuteRequest,
    AgentListEnvelope,
    AgentMetadataResponse,
    ReviewStateEnvelope,
)
from src.state import ReviewStateModel, validate_review_state
from src.source_ingestion import resolve_public_paper_source

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
    """List the currently implemented agents."""
    agents = [
        AgentMetadataResponse(
            name="parser",
            stage="parser",
            version="0.1.0",
            description="Leader parser agent.",
            ready="True",
        ),
        AgentMetadataResponse(
            name="auditor",
            stage="auditor",
            version="0.1.0",
            description="Methodology and data integrity auditor.",
            ready="True",
        ),
        AgentMetadataResponse(
            name="critic",
            stage="critic",
            version="0.1.0",
            description="Red-team gap finder.",
            ready="True",
        ),
        AgentMetadataResponse(
            name="integrator",
            stage="integrator",
            version="0.1.0",
            description="Final synthesis and report generator.",
            ready="True",
        ),
    ]
    return AgentListEnvelope(agents=agents)


@router.post("/{agent_name}/execute", response_model=ReviewStateEnvelope)
def execute_single_agent(
    agent_name: str,
    payload: AgentExecuteRequest,
) -> ReviewStateEnvelope:
    """Execute the parser agent against submitted ReviewState."""
    agent_map = {
        "parser": parser_node,
        "auditor": auditor_node,
        "critic": critic_node,
        "integrator": integrator_node,
    }
    agent_fn = agent_map.get(agent_name)
    if agent_fn is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")

    input_state = validate_review_state(payload.state.model_dump())

    if payload.paper_url:
        source_result = resolve_public_paper_source(payload.paper_url)
        input_state["raw_text"] = (
            source_result.text
            if not input_state["raw_text"]
            else f"{input_state['raw_text']}\n\n{source_result.text}".strip()
        )
        metadata = input_state.setdefault("research_data", {}).setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata.update(source_result.metadata())

    try:
        with _temporary_parser_input_path(payload.parser_input_path):
            updated_state = agent_fn(input_state)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    validated = ReviewStateModel.model_validate(updated_state)
    return ReviewStateEnvelope(state=validated)
