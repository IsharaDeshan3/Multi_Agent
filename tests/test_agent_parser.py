from __future__ import annotations

from src.agents.parser_agent import parser_node
from src.state import create_initial_state


def test_parser_node_reads_file_and_updates_state(tmp_path, monkeypatch) -> None:
    paper = tmp_path / "paper.txt"
    paper.write_text(
        "Research Question: Does structured state help?\n"
        "Methodology: Simulated review pipeline.\n"
        "- Claim A\n"
        "- Claim B\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("PARSER_INPUT_PATH", str(paper))
    monkeypatch.setenv("PARSER_USE_OLLAMA", "false")

    initial = create_initial_state()
    updated = parser_node(initial)

    assert updated["raw_text"]
    assert updated["research_data"]["question"]
    assert isinstance(updated["research_data"]["claims"], list)
    assert any("Parser Agent" in line for line in updated["logs"])
