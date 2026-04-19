from __future__ import annotations

from typing import Optional

from langgraph.graph import END, StateGraph

from src.agents.parser_agent import parser_node
from src.state import ReviewState, create_initial_state, validate_review_state


def _validated_stage_executor(stage: str):
    """Wrap a stage with pre/post contract validation boundaries."""

    def _runner(state: ReviewState) -> ReviewState:
        normalized = validate_review_state(dict(state))
        updated = parser_node(normalized)
        updated["logs"].append(f"Workflow: Stage '{stage}' completed.")
        return validate_review_state(updated)

    return _runner


def build_workflow():
    """Build and compile the parser-only LangGraph workflow."""
    workflow = StateGraph(ReviewState)

    workflow.add_node("parser", _validated_stage_executor("parser"))

    workflow.set_entry_point("parser")
    workflow.add_edge("parser", END)

    return workflow.compile()


COMPILED_WORKFLOW = build_workflow()


def run_full_pipeline(state: Optional[ReviewState] = None) -> ReviewState:
    """Execute the full sequential pipeline with LangGraph."""
    normalized = validate_review_state(dict(state or create_initial_state()))
    result = COMPILED_WORKFLOW.invoke(normalized)
    return validate_review_state(dict(result))


def run_until_stage(stage: str, state: Optional[ReviewState] = None) -> ReviewState:
    """Execute the parser stage; parser is the only supported stage."""
    if stage != "parser":
        raise ValueError(f"Unknown stage: {stage}")

    normalized = validate_review_state(dict(state or create_initial_state()))
    return _validated_stage_executor("parser")(normalized)


def resume_from_stage(stage: str, state: ReviewState) -> ReviewState:
    """Resume execution from parser; only parser is available right now."""
    if stage != "parser":
        raise ValueError(f"Unknown stage: {stage}")

    normalized = validate_review_state(dict(state))
    return _validated_stage_executor("parser")(normalized)
