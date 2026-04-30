from __future__ import annotations

import os

import pytest

from src.agents.parser_agent import parser_node
from src.state import create_initial_state


def test_parser_node_merges_state_and_file_sources(tmp_path, monkeypatch) -> None:
    paper = tmp_path / "paper.txt"
    paper.write_text(
        "Methodology: Simulated review pipeline.\n"
        "Claims:\n"
        "1. File claim one.\n"
        "2. File claim two.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("PARSER_INPUT_PATH", str(paper))
    monkeypatch.setenv("PARSER_USE_OLLAMA", "false")

    initial = create_initial_state(
        raw_text="Research Question: Does structured state help?  \n  "
    )
    updated = parser_node(initial)

    assert "Does structured state help?" in updated["raw_text"]
    assert "Simulated review pipeline." in updated["raw_text"]
    assert updated["research_data"]["question"] == "Does structured state help?"
    assert updated["research_data"]["methodology"] == "Simulated review pipeline."
    assert isinstance(updated["research_data"]["claims"], list)
    assert any("File claim one." in claim for claim in updated["research_data"]["claims"])
    assert updated["research_data"]["metadata"]["mode"] == "deterministic"
    assert str(paper) in updated["research_data"]["metadata"]["sources"]
    assert any("Parser Agent" in line for line in updated["logs"])


def test_parser_node_falls_back_when_ollama_fails(tmp_path, monkeypatch) -> None:
    paper = tmp_path / "paper.txt"
    paper.write_text(
        "Research Question: Can fallback still work?\n"
        "Methodology: Fallback path.\n"
        "- Claim fallback\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("PARSER_INPUT_PATH", str(paper))
    monkeypatch.setenv("PARSER_USE_OLLAMA", "true")
    monkeypatch.setenv("PARSER_OLLAMA_MODEL", "phi3")

    def _fail_structured_output(*args, **kwargs):
        raise RuntimeError("forced ollama failure")

    monkeypatch.setattr("src.agents.parser_agent.ollama_chat_structured", _fail_structured_output)

    initial = create_initial_state()
    updated = parser_node(initial)

    assert updated["research_data"]["question"]
    assert updated["research_data"]["metadata"]["mode"] == "fallback"
    assert any("fallback" in line.lower() for line in updated["logs"])
    assert any("Parser Agent" in line for line in updated["logs"])


def test_parser_node_preserves_state_contract() -> None:
    initial = create_initial_state(raw_text="Research Question: Contract stays stable.")
    updated = parser_node(initial)

    assert set(updated.keys()) == set(initial.keys())
    assert set(updated["research_data"].keys()) >= {"question", "methodology", "claims", "metadata"}


@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_INTEGRATION", "false").lower() != "true",
    reason="Set RUN_OLLAMA_INTEGRATION=true to run the live phi3 parser test.",
)
def test_parser_node_with_phi3_live(tmp_path, monkeypatch) -> None:
    paper = tmp_path / "phi3_input.txt"
    paper.write_text(
        "Research Question: How does phi3 handle structured review extraction?\n"
        "Methodology: A small local end-to-end parser test.\n"
        "Claims:\n"
        "- Structured outputs reduce parse ambiguity.\n"
        "- Deterministic fallbacks keep the pipeline safe.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("PARSER_INPUT_PATH", str(paper))
    monkeypatch.setenv("PARSER_USE_OLLAMA", "true")
    monkeypatch.setenv("PARSER_OLLAMA_MODEL", "phi3")
    monkeypatch.setenv("PARSER_TEMPERATURE", "0")

    updated = parser_node(create_initial_state())

    assert updated["research_data"]["question"]
    assert updated["research_data"]["methodology"]
    assert updated["research_data"]["claims"]
    assert updated["research_data"]["metadata"]["mode"] == "ollama"
