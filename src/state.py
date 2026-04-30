from __future__ import annotations

from typing import Any, Dict, List, TypedDict, cast

from pydantic import BaseModel, ConfigDict, Field


class ReviewState(TypedDict):
    """The global state contract for the multi-agent review system."""

    raw_text: str
    research_data: Dict[str, Any]
    audit_results: Dict[str, Any]
    critique_notes: str
    final_feedback: str
    logs: List[str]


class ResearchDataModel(BaseModel):
    """Structured parser output written into ReviewState.research_data."""

    model_config = ConfigDict(extra="forbid")

    question: str = ""
    methodology: str = ""
    claims: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditResultsModel(BaseModel):
    """Structured auditor output written into ReviewState.audit_results."""

    model_config = ConfigDict(extra="forbid")

    passed: bool = False
    errors: List[str] = Field(default_factory=list)


class ReviewStateModel(BaseModel):
    """Runtime validation model for the shared agent state."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str = ""
    research_data: ResearchDataModel = Field(default_factory=ResearchDataModel)
    audit_results: AuditResultsModel = Field(default_factory=AuditResultsModel)
    critique_notes: str = ""
    final_feedback: str = ""
    logs: List[str] = Field(default_factory=list)


def create_initial_state(raw_text: str = "") -> ReviewState:
    """Create an empty, schema-valid state object.

    Args:
        raw_text: Optional initial text payload.

    Returns:
        ReviewState: A valid initial state.
    """
    model = ReviewStateModel(raw_text=raw_text)
    return cast(ReviewState, model.model_dump())


def validate_review_state(state: Dict[str, Any]) -> ReviewState:
    """Validate and normalize any state-like payload.

    Args:
        state: Candidate state payload.

    Returns:
        ReviewState: Normalized validated state.

    Raises:
        pydantic.ValidationError: If payload does not match schema.
    """
    model = ReviewStateModel.model_validate(state)
    return cast(ReviewState, model.model_dump())
