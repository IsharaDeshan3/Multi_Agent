from __future__ import annotations

from src.agents.auditor_agent import auditor_node
from src.state import create_initial_state


def test_auditor_flags_missing_methodology_and_claims() -> None:
    state = create_initial_state(raw_text="Research Question: Does this work?")
    updated = auditor_node(state)

    assert updated["audit_results"]["passed"] is False
    assert updated["audit_results"]["errors"]
    assert any("Auditor Agent" in line for line in updated["logs"])
