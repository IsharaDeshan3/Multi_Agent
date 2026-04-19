from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.state import ReviewStateModel


class AgentMetadataResponse(BaseModel):
    """Metadata object returned by agent discovery endpoint."""

    name: str
    stage: str
    version: str
    description: str
    ready: str


class AgentExecuteRequest(BaseModel):
    """Payload for direct single-agent execution."""

    state: ReviewStateModel = Field(default_factory=ReviewStateModel)
    parser_input_path: Optional[str] = None


class PipelineExecuteRequest(BaseModel):
    """Payload for workflow execution endpoints."""

    state: Optional[ReviewStateModel] = None
    parser_input_path: Optional[str] = None


class ReviewStateEnvelope(BaseModel):
    """Response wrapper containing the latest validated state."""

    state: ReviewStateModel


class AgentListEnvelope(BaseModel):
    """Response wrapper for registered agent metadata list."""

    agents: List[AgentMetadataResponse]


class HealthResponse(BaseModel):
    """Basic service health response model."""

    status: str
    agents_registered: int


class ContractResponse(BaseModel):
    """Schema introspection response model."""

    contract_name: str
    contract_schema: Dict[str, Any]
