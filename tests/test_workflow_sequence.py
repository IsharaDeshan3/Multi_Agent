from __future__ import annotations

from src.state import create_initial_state
from src.workflow.main import run_full_pipeline


def test_full_pipeline_runs_all_stages() -> None:
    state = create_initial_state(
        raw_text="Research Question: Can the workflow execute?\nMethodology: Test harness."
    )
    updated = run_full_pipeline(state)

    logs_text = "\n".join(updated["logs"])
    assert "Workflow: Stage 'parser' completed." in logs_text
    assert "Workflow: Stage 'auditor' completed." in logs_text
    assert "Workflow: Stage 'critic' completed." in logs_text
    assert "Workflow: Stage 'integrator' completed." in logs_text
