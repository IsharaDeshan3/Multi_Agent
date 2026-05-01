from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.agents.review_prompts import ORCHESTRATOR_WORLDVIEW_PROMPT, PARSER_AGENT_PROMPT
from src.state import ReviewState, validate_review_state
from src.tools import (
    detect_quality_flags,
    extract_research_data,
    extract_urls,
    normalize_markdown_text,
    normalize_text,
    ollama_chat_structured,
    read_document_file,
    score_extraction_confidence,
)


class ParserExtractionModel(BaseModel):
    """Structured parser output used for Ollama-backed extraction."""

    model_config = ConfigDict(extra="forbid")

    question: str = ""
    methodology: str = ""
    claims: List[str] = Field(default_factory=list)
    doi: str = ""
    publication_date: str = ""
    citation_count: Optional[int] = None
    critical_citations: List[str] = Field(default_factory=list)
    link_map: List[str] = Field(default_factory=list)
    extraction_confidence: int = 0
    quality_flags: List[str] = Field(default_factory=list)


def parser_node(state: ReviewState) -> ReviewState:
    """Leader parser agent that extracts key academic sections.

    The parser can run in two modes:
    1. Deterministic extraction (default).
    2. Ollama-backed extraction when PARSER_USE_OLLAMA=true.
    """
    normalized = validate_review_state(dict(state))

    warnings: List[str] = []
    source_labels: List[str] = []

    state_text = normalize_markdown_text(normalized["raw_text"])
    if state_text:
        source_labels.append("state.raw_text")

    file_text = ""
    file_path = os.getenv("PARSER_INPUT_PATH", "data/input_paper.txt")
    if file_path:
        try:
            file_text = normalize_markdown_text(read_document_file(file_path))
            if file_text:
                source_labels.append(file_path)
        except FileNotFoundError as exc:
            if not state_text:
                raise
            warnings.append(f"Parser Agent: file source unavailable ({exc}).")

    content = _merge_text_sources(state_text, file_text)
    if not content and file_path:
        content = normalize_markdown_text(read_document_file(file_path))
        source_labels = [file_path]

    parsed_data: Dict[str, Any]
    mode = "deterministic"

    if os.getenv("PARSER_USE_OLLAMA", "true").lower() == "true":
        try:
            parsed_data = _extract_with_ollama(content)
            mode = "ollama"
        except Exception as exc:
            parsed_data = extract_research_data(content)
            warnings.append(f"Parser Agent: Ollama fallback triggered ({exc}).")
            mode = "fallback"
    else:
        parsed_data = extract_research_data(content)

    existing_metadata = normalized["research_data"].get("metadata", {})
    if not isinstance(existing_metadata, dict):
        existing_metadata = {}

    link_map = _merge_unique(_coerce_string_list(parsed_data.get("link_map")))
    if not link_map:
        link_map = extract_urls(content)

    critical_citations = _merge_unique(_coerce_string_list(parsed_data.get("critical_citations")))
    if not critical_citations:
        critical_citations = link_map[:3]

    quality_flags = _merge_unique(_coerce_string_list(parsed_data.get("quality_flags")))
    quality_flags.extend(detect_quality_flags(content))
    quality_flags = _merge_unique(quality_flags)
    if any(flag in {"paywall-noise", "corrupted-encoding", "table-extraction-risk", "equation-extraction-risk"} for flag in quality_flags):
        warnings.append("Parser Agent: source quality risk detected during extraction.")

    doi = _extract_doi(parsed_data.get("doi") or content)
    publication_date = _extract_publication_date(parsed_data.get("publication_date") or content)
    citation_count = _extract_citation_count(content, parsed_data.get("citation_count"))

    extraction_confidence = parsed_data.get("extraction_confidence") or score_extraction_confidence(
        content,
        question=str(parsed_data.get("question", "")),
        methodology=str(parsed_data.get("methodology", "")),
        claims=_coerce_string_list(parsed_data.get("claims")),
        link_map=link_map,
        quality_flags=quality_flags,
    )

    parsed_data.update(
        {
            "question": normalize_text(str(parsed_data.get("question", ""))),
            "methodology": normalize_text(str(parsed_data.get("methodology", ""))),
            "claims": [normalize_text(item) for item in _coerce_string_list(parsed_data.get("claims"))],
            "doi": doi,
            "publication_date": publication_date,
            "citation_count": citation_count,
            "critical_citations": critical_citations,
            "link_map": link_map,
            "extraction_confidence": max(1, min(10, int(extraction_confidence))),
            "quality_flags": quality_flags,
            "source_format": "markdown",
        }
    )

    parsed_data["metadata"] = {
        **existing_metadata,
        "mode": mode,
        "sources": source_labels,
        "warnings": warnings,
        "cleaned_text": True,
        "governance": "COPE",
        "source_format": "markdown",
        "extraction_confidence": parsed_data["extraction_confidence"],
        "link_map": link_map,
        "quality_flags": quality_flags,
    }

    normalized["raw_text"] = content
    normalized["research_data"] = parsed_data

    if warnings:
        for warning in warnings:
            normalized["logs"].append(warning)

    normalized["logs"].append(
        f"Parser Agent: Parsed research data from {', '.join(source_labels) if source_labels else 'unknown source'} using {mode} mode with confidence {parsed_data['extraction_confidence']}/10."
    )

    return validate_review_state(normalized)


def _extract_with_ollama(raw_text: str) -> Dict[str, Any]:
    """Use Ollama structured outputs to extract parser output."""
    ollama_model = os.getenv("PARSER_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "phi3"))
    ollama_base_url = os.getenv("PARSER_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    temperature = float(os.getenv("PARSER_TEMPERATURE", "0"))

    prompt = (
        f"{ORCHESTRATOR_WORLDVIEW_PROMPT}\n\n"
        f"{PARSER_AGENT_PROMPT}\n\n"
        "Extract the following paper text into JSON with keys: "
        "question (string), methodology (string), claims (array of strings), "
        "doi (string), publication_date (string), citation_count (integer or null), "
        "critical_citations (array of strings), link_map (array of strings), "
        "extraction_confidence (integer 1-10), and quality_flags (array of strings). "
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
        "doi": normalize_text(structured.doi),
        "publication_date": normalize_text(structured.publication_date),
        "citation_count": structured.citation_count,
        "critical_citations": [normalize_text(item) for item in structured.critical_citations if normalize_text(item)],
        "link_map": [normalize_text(item) for item in structured.link_map if normalize_text(item)],
        "extraction_confidence": max(1, min(10, structured.extraction_confidence or 0)),
        "quality_flags": [normalize_text(item) for item in structured.quality_flags if normalize_text(item)],
    }


def _merge_text_sources(state_text: str, file_text: str) -> str:
    """Combine the state text and file text without losing either source."""
    parts = []
    if state_text:
        parts.append(state_text)
    if file_text and file_text != state_text:
        parts.append(file_text)
    return normalize_markdown_text("\n\n".join(parts))


def _coerce_string_list(value: Any) -> List[str]:
    """Coerce a parser field into a list of non-empty strings."""
    if isinstance(value, list):
        return [normalize_text(str(item)) for item in value if normalize_text(str(item))]
    if isinstance(value, str):
        normalized = normalize_text(value)
        return [normalized] if normalized else []
    return []


def _merge_unique(items: List[str]) -> List[str]:
    """Deduplicate strings while preserving order."""
    seen = set()
    result: List[str] = []
    for item in items:
        cleaned = normalize_text(item)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _extract_doi(raw_text: Any) -> str:
    """Extract a DOI-like identifier from text."""
    if not isinstance(raw_text, str):
        return ""
    match = re.search(r"10\.\d{4,9}/\S+", raw_text, flags=re.IGNORECASE)
    return normalize_text(match.group(0)) if match else ""


def _extract_publication_date(raw_text: Any) -> str:
    """Extract a publication date or fallback year from text."""
    if not isinstance(raw_text, str):
        return ""

    date_match = re.search(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b", raw_text)
    if date_match:
        return date_match.group(0)

    year_match = re.search(r"\b(?:19|20)\d{2}\b", raw_text)
    return year_match.group(0) if year_match else ""


def _extract_citation_count(raw_text: str, parsed_value: Any) -> Optional[int]:
    """Extract a citation count if the source text exposes one."""
    if isinstance(parsed_value, int):
        return parsed_value

    match = re.search(r"(?:cited by|citation count|citations?)\s*[:=]?\s*(\d+)", raw_text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None
