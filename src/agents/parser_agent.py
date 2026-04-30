from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from src.state import ReviewState, validate_review_state
from src.tools import (
    extract_research_data,
    normalize_text,
    ollama_chat_structured,
    read_document_file,
)


class ParserExtractionModel(BaseModel):
    """Structured parser output used for Ollama-backed extraction."""

    model_config = ConfigDict(extra="forbid")

    question: str = ""
    methodology: str = ""
    claims: List[str] = Field(default_factory=list)


def parser_node(state: ReviewState) -> ReviewState:
    """Leader parser agent that extracts key academic sections.

    The parser can run in two modes:
    1. Deterministic extraction (default).
    2. Ollama-backed extraction when PARSER_USE_OLLAMA=true.
    """
    normalized = validate_review_state(dict(state))

    warnings: List[str] = []
    source_labels: List[str] = []

    state_text = normalize_text(normalized["raw_text"])
    if state_text:
        source_labels.append("state.raw_text")

    file_text = ""
    file_path = os.getenv("PARSER_INPUT_PATH", "data/input_paper.txt")
    if file_path:
        try:
            file_text = normalize_text(read_document_file(file_path))
            if file_text:
                source_labels.append(file_path)
        except FileNotFoundError as exc:
            if not state_text:
                raise
            warnings.append(f"Parser Agent: file source unavailable ({exc}).")

    content = _merge_text_sources(state_text, file_text)
    if not content and file_path:
        content = normalize_text(read_document_file(file_path))
        source_labels = [file_path]

    parsed_data: Dict[str, Any]
    mode = "deterministic"

    if os.getenv("PARSER_USE_OLLAMA", "false").lower() == "true":
        try:
            parsed_data = _extract_with_ollama(content)
            mode = "ollama"
        except Exception as exc:  # pragma: no cover - fallback branch
            parsed_data = extract_research_data(content)
            warnings.append(f"Parser Agent: Ollama fallback triggered ({exc}).")
            mode = "fallback"
    else:
        parsed_data = extract_research_data(content)

    parsed_data["metadata"] = {
        "mode": mode,
        "sources": source_labels,
        "warnings": warnings,
        "cleaned_text": True,
    }

    normalized["raw_text"] = content
    normalized["research_data"] = parsed_data

    if warnings:
        for warning in warnings:
            normalized["logs"].append(warning)

    normalized["logs"].append(
        f"Parser Agent: Parsed research data from {', '.join(source_labels) if source_labels else 'unknown source'} using {mode} mode."
    )

    return validate_review_state(normalized)


def _extract_with_ollama(raw_text: str) -> Dict[str, Any]:
    """Use Ollama structured outputs to extract parser output."""
    ollama_model = os.getenv("PARSER_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "phi3"))
    ollama_base_url = os.getenv("PARSER_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    temperature = float(os.getenv("PARSER_TEMPERATURE", "0"))

    prompt = (
        "Extract the following paper text into JSON with keys: "
        "question (string), methodology (string), claims (array of strings). "
        "Return JSON only and preserve the original meaning.\n\n"
        f"Paper text:\n{raw_text}"
    )
    data = ollama_chat_structured(
        prompt=prompt,
        schema=ParserExtractionModel.model_json_schema(),
        model=ollama_model,
        base_url=ollama_base_url,
        temperature=temperature,
    )

    structured = ParserExtractionModel.model_validate(data)
    return {
        "question": normalize_text(structured.question),
        "methodology": normalize_text(structured.methodology),
        "claims": [normalize_text(item) for item in structured.claims if normalize_text(item)],
    }


def _merge_text_sources(state_text: str, file_text: str) -> str:
    """Combine the state text and file text without losing either source."""
    parts = []
    if state_text:
        parts.append(state_text)
    if file_text and file_text != state_text:
        parts.append(file_text)
    return normalize_text("\n\n".join(parts))
