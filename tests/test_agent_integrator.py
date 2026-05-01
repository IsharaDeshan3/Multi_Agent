from __future__ import annotations

import pytest

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


def test_integrator_uses_phi3_when_available(monkeypatch) -> None:
    state = create_initial_state(raw_text="Research Question: Does phi3 synthesize reports?")
    state["research_data"] = {
        "question": "Does phi3 synthesize reports?",
        "methodology": "Model-backed synthesis.",
        "claims": ["Claim one."],
        "critical_citations": ["https://example.com/cite"],
        "extraction_confidence": 8,
        "metadata": {},
    }
    state["audit_results"] = {"passed": True, "errors": []}
    state["critique_notes"] = "Critical Review Notes\n- Model feedback looks strong."

    monkeypatch.setenv("INTEGRATOR_USE_OLLAMA", "true")
    monkeypatch.setenv("OLLAMA_MODEL", "phi3")
    monkeypatch.setattr(
        "src.agents.integrator_agent.ollama_chat_structured",
        lambda **kwargs: {"final_feedback": "Model generated final report."},
    )

    updated = integrator_node(state)

    assert updated["final_feedback"] == "Model generated final report."
    assert updated["research_data"]["metadata"]["integrator_mode"] == "ollama"
    assert any("ollama synthesis completed" in line.lower() for line in updated["logs"])
