from __future__ import annotations

from src.agents.critic_agent import critic_node
from src.state import create_initial_state


def test_critic_emits_gap_notes() -> None:
    state = create_initial_state(
        raw_text="Research Question: Can this work?\nMethodology: Simulated test."
    )
    updated = critic_node(state)

    assert "Limitations" in updated["critique_notes"]
    assert any("Critic Agent" in line for line in updated["logs"])
