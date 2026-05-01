from __future__ import annotations

import json
import os

import pytest

from src.agents.parser_agent import parser_node
from src.state import create_initial_state
from src.tools import ollama_chat_structured


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
    assert updated["research_data"]["source_format"] == "markdown"
    assert updated["research_data"]["extraction_confidence"] >= 1
    assert isinstance(updated["research_data"]["link_map"], list)
    assert updated["research_data"]["metadata"]["mode"] == "deterministic"
    assert str(paper) in updated["research_data"]["metadata"]["sources"]
    assert any("Parser Agent" in line for line in updated["logs"])


def test_parser_node_falls_back_when_ollama_model_is_unavailable(tmp_path, monkeypatch) -> None:
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

    assert updated["research_data"]["metadata"]["mode"] == "fallback"
    assert any("fallback" in line.lower() for line in updated["logs"])


def test_parser_node_uses_phi3_when_available(tmp_path, monkeypatch) -> None:
    paper = tmp_path / "paper.txt"
    paper.write_text(
        "Research Question: Will phi3 extract structured output?\n"
        "Methodology: A model-backed parser check.\n"
        "Claims:\n"
        "- Model output is used.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("PARSER_INPUT_PATH", str(paper))
    monkeypatch.setenv("PARSER_USE_OLLAMA", "true")
    monkeypatch.setenv("PARSER_OLLAMA_MODEL", "phi3")
    monkeypatch.setenv("PARSER_TEMPERATURE", "0")

    monkeypatch.setattr(
        "src.agents.parser_agent.ollama_chat_structured",
        lambda **kwargs: {
            "question": "Will phi3 extract structured output?",
            "methodology": "A model-backed parser check.",
            "claims": ["Model output is used."],
            "doi": "10.1000/model",
            "publication_date": "2026-05-01",
            "citation_count": 12,
            "critical_citations": ["https://example.com/cite"],
            "link_map": ["https://example.com/model"],
            "extraction_confidence": 9,
            "quality_flags": [],
        },
    )

    updated = parser_node(create_initial_state())

    assert updated["research_data"]["metadata"]["mode"] == "ollama"
    assert updated["research_data"]["question"] == "Will phi3 extract structured output?"
    assert any("phi3" in line.lower() or "ollama" in line.lower() for line in updated["logs"])


def test_ollama_structured_requests_force_cpu(monkeypatch) -> None:
    captured = {}

    def _fake_check(*args, **kwargs):
        return True

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "question": "Q",
                                "methodology": "M",
                                "claims": [],
                                "doi": "",
                                "publication_date": "",
                                "citation_count": None,
                                "critical_citations": [],
                                "link_map": [],
                                "extraction_confidence": 1,
                                "quality_flags": [],
                            }
                        )
                    }
                }
            ).encode("utf-8")

    def _fake_urlopen(req, timeout=0):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr("src.tools.ollama_model_is_available", _fake_check)
    monkeypatch.setattr("src.tools.request.urlopen", _fake_urlopen)

    result = ollama_chat_structured(
        prompt="Extract structured data.",
        schema={"type": "object"},
        model="phi3",
        base_url="http://localhost:11434",
        temperature=0,
    )

    assert captured["payload"]["options"]["num_gpu"] == 0
    assert captured["payload"]["options"]["temperature"] == 0
    assert result["question"] == "Q"


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
