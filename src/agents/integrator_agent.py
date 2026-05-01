from __future__ import annotations

import json
import os
from typing import List

from pydantic import BaseModel, ConfigDict

from src.agents.review_prompts import ORCHESTRATOR_WORLDVIEW_PROMPT, SYNTHESIZER_AGENT_PROMPT
from src.state import ReviewState, validate_review_state
from src.tools import normalize_text, ollama_chat_structured


class IntegratorReviewModel(BaseModel):
    """Structured synthesis output returned by the model-backed integrator."""

    model_config = ConfigDict(extra="forbid")

    final_feedback: str = ""


def integrator_node(state: ReviewState) -> ReviewState:
    """Synthesize the full review into a structured report."""
    normalized = validate_review_state(dict(state))
    research_data = normalized.get("research_data", {})
    audit_results = normalized.get("audit_results", {})
    critique_notes = normalized.get("critique_notes", "")

    deterministic_feedback = _build_deterministic_feedback(research_data, audit_results, critique_notes)
    model_review = IntegratorReviewModel()
    mode = "deterministic"

    if _use_ollama():
        try:
            model_review = _integrate_with_ollama(normalized)
            mode = "ollama"
        except Exception as exc:
            normalized["logs"].append(f"Integrator Agent: Ollama fallback triggered ({exc}).")
            mode = "fallback"

    final_feedback = normalize_text(model_review.final_feedback) or deterministic_feedback

    metadata = normalized["research_data"].setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["integrator_mode"] = mode

    normalized["final_feedback"] = final_feedback
    normalized["logs"].append(
        "Integrator Agent: "
        + (f"{mode} synthesis completed. " if mode != "deterministic" else "")
        + "Final report generated."
    )

    return validate_review_state(normalized)


def _integrate_with_ollama(state: ReviewState) -> IntegratorReviewModel:
    """Use phi3 to synthesize the final report."""
    ollama_model = os.getenv("INTEGRATOR_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "phi3"))
    ollama_base_url = os.getenv("INTEGRATOR_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    temperature = float(os.getenv("INTEGRATOR_TEMPERATURE", "0"))

    prompt = (
        f"{ORCHESTRATOR_WORLDVIEW_PROMPT}\n\n"
        f"{SYNTHESIZER_AGENT_PROMPT}\n\n"
        "Synthesize a final review report and return JSON only with key final_feedback (string). "
        "Use the audit results and critique notes to generate a concise report.\n\n"
        f"Research data: {json.dumps(state.get('research_data', {}), ensure_ascii=False)}\n\n"
        f"Audit results: {json.dumps(state.get('audit_results', {}), ensure_ascii=False)}\n\n"
        f"Critique notes:\n{state.get('critique_notes', '')}"
    )

    data = ollama_chat_structured(
        prompt=prompt,
        schema=IntegratorReviewModel.model_json_schema(),
        model=ollama_model,
        base_url=ollama_base_url,
        temperature=temperature,
    )

    return IntegratorReviewModel.model_validate(data)


def _build_deterministic_feedback(research_data, audit_results, critique_notes: str) -> str:
    """Build the existing deterministic synthesis report."""
    passed = bool(audit_results.get("passed"))
    errors = audit_results.get("errors", []) or []

    extraction_confidence = int(research_data.get("extraction_confidence", 0) or 0)
    novelty_score = _score_novelty(critique_notes)
    rigor_score = 8 if passed else max(3, 8 - len(errors) * 2)
    clarity_score = max(3, min(10, 4 + extraction_confidence))

    keep_recommendation = "Keep" if passed and extraction_confidence >= 6 else "Discard"
    verdict = _final_verdict(passed, len(errors), critique_notes)

    evidence_log = _build_evidence_log(errors, critique_notes)

    return (
        "Review Evaluation File\n"
        "Executive Summary:\n"
        f"- Recommendation: {keep_recommendation}\n\n"
        "Technical Scorecard:\n"
        f"- Novelty: {novelty_score}/10\n"
        f"- Rigor: {rigor_score}/10\n"
        f"- Clarity: {clarity_score}/10\n\n"
        "Evidence Log:\n"
        f"{evidence_log}\n\n"
        "Final Verdict:\n"
        f"- {verdict}\n"
    )


def _use_ollama() -> bool:
    """Return whether the integrator should prefer the phi3-backed path."""
    return os.getenv("INTEGRATOR_USE_OLLAMA", "true").lower() == "true"


def _score_novelty(critique_notes: str) -> int:
    lowered = critique_notes.lower()
    if "disruptive" in lowered:
        return 8
    if "incremental" in lowered:
        return 5
    return 6


def _final_verdict(passed: bool, error_count: int, critique_notes: str) -> str:
    lowered = critique_notes.lower()
    if not passed and error_count >= 3:
        return "Rejection"
    if not passed:
        return "Major Revision"
    if any(keyword in lowered for keyword in ["missing", "not", "unclear", "limited"]):
        return "Minor Revision"
    return "Minor Revision"


def _build_evidence_log(errors: list[str], critique_notes: str) -> str:
    entries = [f"- {normalize_text(error)}" for error in errors]
    critique_lines = [
        line.strip() for line in critique_notes.splitlines() if line.strip().startswith("-")
    ]
    entries.extend(critique_lines[:3])
    return "\n".join(entries) if entries else "- No critical issues logged."
