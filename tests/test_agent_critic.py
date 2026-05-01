from __future__ import annotations

import pytest

from src.agents.critic_agent import critic_node
from src.state import create_initial_state


def test_critic_emits_gap_notes() -> None:
    state = create_initial_state(
        raw_text="Research Question: Can this work?\nMethodology: Simulated test."
    )
    state["research_data"] = {
        "question": "Can this work?",
        "methodology": "Simulated test.",
        "claims": ["Claim one."],
        "critical_citations": ["https://example.com/cite"],
        "metadata": {},
    }
    updated = critic_node(state)

    assert "Limitations" in updated["critique_notes"]
    assert any("Critic Agent" in line for line in updated["logs"])


def test_critic_uses_phi3_when_available(monkeypatch) -> None:
    state = create_initial_state(
        raw_text=(
            "Research Question: Can phi3 review this?\n"
            "Methodology: Model-backed critique.\n"
            "Limitations: Discussed.\n"
            "Ethics: Discussed.\n"
            "Failure cases: Discussed."
        )
    )
    state["research_data"] = {
        "question": "Can phi3 review this?",
        "methodology": "Model-backed critique.",
        "claims": ["Claim one."],
        "critical_citations": ["https://example.com/cite"],
        "metadata": {},
    }

    monkeypatch.setenv("CRITIC_USE_OLLAMA", "true")
    monkeypatch.setenv("OLLAMA_MODEL", "phi3")
    monkeypatch.setattr(
        "src.agents.critic_agent.ollama_chat_structured",
        lambda **kwargs: {
            "critique_points": ["Model gap detected."],
            "novelty": "disruptive",
        },
    )

    updated = critic_node(state)

    assert "Model gap detected." in updated["critique_notes"]
    assert "Novelty estimate: disruptive." in updated["critique_notes"]
    assert updated["research_data"]["metadata"]["critic_mode"] == "ollama"
    assert any("ollama review completed" in line.lower() for line in updated["logs"])
