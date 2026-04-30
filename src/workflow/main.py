from __future__ import annotations

from typing import Optional

from langgraph.graph import END, StateGraph

from src.agents.auditor_agent import auditor_node
from src.agents.critic_agent import critic_node
from src.agents.integrator_agent import integrator_node
from src.agents.parser_agent import parser_node
from src.state import ReviewState, create_initial_state, validate_review_state


STAGE_SEQUENCE = [
    ("parser", parser_node),
    ("auditor", auditor_node),
    ("critic", critic_node),
    ("integrator", integrator_node),
]


def _validated_stage_executor(stage: str, stage_fn):
    """Wrap a stage with pre/post contract validation boundaries."""

    def _runner(state: ReviewState) -> ReviewState:
        normalized = validate_review_state(dict(state))
        updated = stage_fn(normalized)
        updated["logs"].append(f"Workflow: Stage '{stage}' completed.")
        return validate_review_state(updated)

    return _runner


def build_workflow():
    """Build and compile the sequential LangGraph workflow."""
    workflow = StateGraph(ReviewState)

    for stage_name, stage_fn in STAGE_SEQUENCE:
        workflow.add_node(stage_name, _validated_stage_executor(stage_name, stage_fn))

    workflow.set_entry_point("parser")
    for index, (stage_name, _) in enumerate(STAGE_SEQUENCE):
        if index == len(STAGE_SEQUENCE) - 1:
            workflow.add_edge(stage_name, END)
        else:
            workflow.add_edge(stage_name, STAGE_SEQUENCE[index + 1][0])

    return workflow.compile()


COMPILED_WORKFLOW = build_workflow()


def run_full_pipeline(state: Optional[ReviewState] = None) -> ReviewState:
    """Execute the full sequential pipeline with LangGraph."""
    normalized = validate_review_state(dict(state or create_initial_state()))
    result = COMPILED_WORKFLOW.invoke(normalized)
    return validate_review_state(dict(result))


def run_until_stage(stage: str, state: Optional[ReviewState] = None) -> ReviewState:
    """Execute the pipeline up to a requested stage."""
    stage_names = [name for name, _ in STAGE_SEQUENCE]
    if stage not in stage_names:
        raise ValueError(f"Unknown stage: {stage}")

    normalized = validate_review_state(dict(state or create_initial_state()))
    for stage_name, stage_fn in STAGE_SEQUENCE:
        normalized = _validated_stage_executor(stage_name, stage_fn)(normalized)
        if stage_name == stage:
            return normalized

    return normalized


def resume_from_stage(stage: str, state: ReviewState) -> ReviewState:
    """Resume execution from the requested stage."""
    stage_names = [name for name, _ in STAGE_SEQUENCE]
    if stage not in stage_names:
        raise ValueError(f"Unknown stage: {stage}")

    normalized = validate_review_state(dict(state))
    start = False
    for stage_name, stage_fn in STAGE_SEQUENCE:
        if stage_name == stage:
            start = True
        if start:
            normalized = _validated_stage_executor(stage_name, stage_fn)(normalized)

    return normalized
