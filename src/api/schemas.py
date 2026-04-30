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
    paper_url: Optional[str] = None


class PipelineExecuteRequest(BaseModel):
    """Payload for workflow execution endpoints."""

    state: Optional[ReviewStateModel] = None
    parser_input_path: Optional[str] = None
    paper_url: Optional[str] = None


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


class RunStatusResponse(BaseModel):
    """Status payload for a background pipeline run."""

    run_id: str
    status: str
    current_stage: str
    stage_index: int
    stage_total: int
    started_at: str
    updated_at: str
    messages: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    result_state: Optional[ReviewStateModel] = None
    source_url: Optional[str] = None
    resolved_source_url: Optional[str] = None
    source_content_type: Optional[str] = None
    source_artifact_path: Optional[str] = None
    source_status: Optional[str] = None
