from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from src.agents.review_prompts import AUDITOR_AGENT_PROMPT, ORCHESTRATOR_WORLDVIEW_PROMPT
from src.state import ReviewState, validate_review_state
from src.tools import normalize_text, ollama_chat_structured


class AuditorReviewModel(BaseModel):
    """Structured review output returned by the model-backed auditor."""

    model_config = ConfigDict(extra="forbid")

    passed: bool = False
    errors: List[str] = Field(default_factory=list)


def auditor_node(state: ReviewState) -> ReviewState:
    """Audit methodology and data integrity signals.

    The auditor performs deterministic checks on the extracted methodology,
    claims, and metric usage. It records any violations in audit_results.
    """
    normalized = validate_review_state(dict(state))
    research_data = normalized.get("research_data", {})

    deterministic_errors = _deterministic_audit_errors(normalized)
    model_review = AuditorReviewModel()
    mode = "deterministic"

    if _use_ollama():
        try:
            model_review = _audit_with_ollama(normalized)
            mode = "ollama"
        except Exception as exc:
            normalized["logs"].append(f"Auditor Agent: Ollama fallback triggered ({exc}).")
            mode = "fallback"

    errors = _merge_unique([*model_review.errors, *deterministic_errors])
    passed = bool(model_review.passed) and not deterministic_errors and not errors

    normalized["audit_results"] = {
        "passed": passed,
        "errors": errors,
    }

    metadata = normalized["research_data"].setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["auditor_mode"] = mode

    normalized["logs"].append(
        "Auditor Agent: "
        + (f"{mode} review completed. " if mode != "deterministic" else "")
        + ("All checks passed." if not errors else f"Found {len(errors)} issue(s).")
    )

    return validate_review_state(normalized)


def _audit_with_ollama(state: ReviewState) -> AuditorReviewModel:
    """Use phi3 to produce a structured audit review."""
    ollama_model = os.getenv("AUDITOR_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "phi3"))
    ollama_base_url = os.getenv("AUDITOR_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    temperature = float(os.getenv("AUDITOR_TEMPERATURE", "0"))

    prompt = (
        f"{ORCHESTRATOR_WORLDVIEW_PROMPT}\n\n"
        f"{AUDITOR_AGENT_PROMPT}\n\n"
        "Review the extracted manuscript state and return JSON only with keys: "
        "passed (boolean) and errors (array of strings). "
        "Prefer concise, actionable errors.\n\n"
        f"Extracted research data: {json.dumps(state.get('research_data', {}), ensure_ascii=False)}\n\n"
        f"Paper text:\n{state.get('raw_text', '')}"
    )

    data = ollama_chat_structured(
        prompt=prompt,
        schema=AuditorReviewModel.model_json_schema(),
        model=ollama_model,
        base_url=ollama_base_url,
        temperature=temperature,
    )

    return AuditorReviewModel.model_validate(data)


def _deterministic_audit_errors(state: ReviewState) -> List[str]:
    """Run the existing local audit checks as a fallback and guardrail."""
    research_data = state.get("research_data", {})
    errors: List[str] = []

    methodology = normalize_text(str(research_data.get("methodology", "")))
    claims = research_data.get("claims") or []
    extraction_confidence = int(research_data.get("extraction_confidence", 0) or 0)

    if not methodology or methodology == "Methodology not explicitly identified.":
        errors.append("Methodology is missing or too vague.")

    if not claims or claims == ["No explicit claims detected."]:
        errors.append("Claims section is missing or under-specified.")

    if extraction_confidence and extraction_confidence < 4:
        errors.append("Extraction confidence is low; review source quality.")

    metrics = _extract_metrics(state.get("raw_text", ""))
    if not metrics:
        errors.append("No standard evaluation metrics detected in the manuscript.")

    return errors


def _use_ollama() -> bool:
    """Return whether the auditor should prefer the phi3-backed path."""
    return os.getenv("AUDITOR_USE_OLLAMA", "true").lower() == "true"


def _merge_unique(items: List[str]) -> List[str]:
    """Deduplicate strings while preserving order."""
    seen = set()
    result: List[str] = []
    for item in items:
        cleaned = normalize_text(str(item))
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _extract_metrics(raw_text: str) -> List[str]:
    """Detect common quantitative metrics mentioned in the paper."""
    candidates = [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "f1-score",
        "auc",
        "roc",
        "bleu",
        "rouge",
        "p-value",
        "p value",
        "rmse",
        "mae",
        "mse",
    ]
    lowered = raw_text.lower()
    found = []

    for metric in candidates:
        if metric in lowered:
            found.append(metric)

    numeric_metric = re.search(r"\b\d+(?:\.\d+)?%\b", raw_text)
    if numeric_metric and not found:
        found.append("percentage")

    return list(dict.fromkeys(found))
