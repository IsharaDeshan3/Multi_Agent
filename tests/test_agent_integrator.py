from __future__ import annotations

from src.agents.integrator_agent import integrator_node
from src.state import create_initial_state


def test_integrator_generates_report() -> None:
    state = create_initial_state(raw_text="Research Question: Does it scale?")
    state["audit_results"] = {"passed": False, "errors": ["Missing methodology."]}
    state["critique_notes"] = "Critical Review Notes\n- Limitations are not discussed."

    updated = integrator_node(state)

    assert "Review Evaluation File" in updated["final_feedback"]
    assert "Final Verdict" in updated["final_feedback"]
    assert any("Integrator Agent" in line for line in updated["logs"])
