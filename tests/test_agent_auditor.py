from __future__ import annotations

import pytest

from src.agents.auditor_agent import auditor_node
from src.state import create_initial_state


def test_auditor_flags_missing_methodology_and_claims(monkeypatch) -> None:
    monkeypatch.setenv("AUDITOR_USE_OLLAMA", "false")

    state = create_initial_state(raw_text="Research Question: Does this work?")
    state["research_data"] = {
        "question": "Does this work?",
        "methodology": "",
        "claims": [],
        "extraction_confidence": 2,
        "critical_citations": [],
        "link_map": [],
        "quality_flags": [],
        "metadata": {},
    }
    updated = auditor_node(state)

    assert updated["audit_results"]["passed"] is False
    assert updated["audit_results"]["errors"]
    assert any("Auditor Agent" in line for line in updated["logs"])


def test_auditor_uses_phi3_when_available(monkeypatch) -> None:
    state = create_initial_state(
        raw_text="Research Question: Does this work?\nResults: accuracy 93% on the benchmark."
    )
    state["research_data"] = {
        "question": "Does this work?",
        "methodology": "Model-backed audit method.",
        "claims": ["Claim one."],
        "extraction_confidence": 8,
        "critical_citations": [],
        "link_map": [],
        "quality_flags": [],
        "metadata": {},
    }

    monkeypatch.setenv("AUDITOR_USE_OLLAMA", "true")
    monkeypatch.setenv("OLLAMA_MODEL", "phi3")
    monkeypatch.setattr(
        "src.agents.auditor_agent.ollama_chat_structured",
        lambda **kwargs: {"passed": True, "errors": []},
    )

    updated = auditor_node(state)

    assert updated["audit_results"]["passed"] is True
    assert updated["audit_results"]["errors"] == []
    assert updated["research_data"]["metadata"]["auditor_mode"] == "ollama"
    assert updated["research_data"]["metadata"].get("mode") in {None, "deterministic"}
    assert any("ollama review completed" in line.lower() for line in updated["logs"])
