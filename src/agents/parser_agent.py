from __future__ import annotations

import json
import os
from typing import Any, Dict

from src.state import ReviewState, validate_review_state
from src.tools import extract_research_data, ollama_generate, read_paper_file


def parser_node(state: ReviewState) -> ReviewState:
    """Leader parser agent that extracts key academic sections.

    The parser can run in two modes:
    1. Deterministic extraction (default).
    2. Ollama-backed extraction when PARSER_USE_OLLAMA=true.
    """
    normalized = validate_review_state(dict(state))

    source = "state.raw_text"
    content = normalized["raw_text"].strip()

    if not content:
        file_path = os.getenv("PARSER_INPUT_PATH", "data/input_paper.txt")
        content = read_paper_file(file_path)
        source = file_path

    parsed_data: Dict[str, Any]
    mode = "deterministic"

    if os.getenv("PARSER_USE_OLLAMA", "false").lower() == "true":
        try:
            parsed_data = _extract_with_ollama(content)
            mode = "ollama"
        except Exception as exc:  # pragma: no cover - fallback branch
            parsed_data = extract_research_data(content)
            normalized["logs"].append(f"Parser Agent: Ollama fallback triggered ({exc}).")
            mode = "fallback"
    else:
        parsed_data = extract_research_data(content)

    normalized["raw_text"] = content
    normalized["research_data"] = parsed_data
    normalized["logs"].append(
        f"Parser Agent: Parsed research data successfully from {source} using {mode} mode."
    )

    return validate_review_state(normalized)


def _extract_with_ollama(raw_text: str) -> Dict[str, Any]:
    """Use Ollama to extract parser output as strict JSON."""
    prompt = (
        "Extract the following paper text into JSON with keys: "
        "question (string), methodology (string), claims (array of strings). "
        "Return JSON only.\n\n"
        f"Paper text:\n{raw_text}"
    )
    raw_response = ollama_generate(prompt=prompt)
    data = json.loads(raw_response)

    if not isinstance(data, dict):
        raise ValueError("Ollama response is not a JSON object.")

    question = str(data.get("question", "")).strip()
    methodology = str(data.get("methodology", "")).strip()
    claims = data.get("claims", [])

    if not isinstance(claims, list):
        raise ValueError("Ollama claims output is not a list.")

    normalized_claims = [str(item).strip() for item in claims if str(item).strip()]

    return {
        "question": question,
        "methodology": methodology,
        "claims": normalized_claims,
    }
