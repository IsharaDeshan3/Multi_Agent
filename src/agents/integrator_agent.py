from __future__ import annotations

from src.state import ReviewState, validate_review_state
from src.tools import normalize_text


def integrator_node(state: ReviewState) -> ReviewState:
    """Synthesize the full review into a structured report."""
    normalized = validate_review_state(dict(state))
    research_data = normalized.get("research_data", {})
    audit_results = normalized.get("audit_results", {})
    critique_notes = normalized.get("critique_notes", "")

    passed = bool(audit_results.get("passed"))
    errors = audit_results.get("errors", []) or []

    extraction_confidence = int(research_data.get("extraction_confidence", 0) or 0)
    novelty_score = _score_novelty(critique_notes)
    rigor_score = 8 if passed else max(3, 8 - len(errors) * 2)
    clarity_score = max(3, min(10, 4 + extraction_confidence))

    keep_recommendation = "Keep" if passed and extraction_confidence >= 6 else "Discard"
    verdict = _final_verdict(passed, len(errors), critique_notes)

    evidence_log = _build_evidence_log(errors, critique_notes)

    final_feedback = (
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

    normalized["final_feedback"] = normalize_text(final_feedback)
    normalized["logs"].append("Integrator Agent: Final report generated.")

    return validate_review_state(normalized)


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
