from __future__ import annotations

from typing import List

from src.state import ReviewState, validate_review_state
from src.tools import normalize_text


def critic_node(state: ReviewState) -> ReviewState:
    """Red-team the manuscript for gaps, logical leaps, and omissions."""
    normalized = validate_review_state(dict(state))
    research_data = normalized.get("research_data", {})

    critiques: List[str] = []

    raw_text = normalized.get("raw_text", "")
    lowered = raw_text.lower()

    if "limitations" not in lowered:
        critiques.append("Limitations are not explicitly discussed.")
    if "ethical" not in lowered and "ethics" not in lowered:
        critiques.append("Ethical considerations are not addressed.")
    if "failure" not in lowered and "robust" not in lowered:
        critiques.append("Failure cases or robustness checks are not described.")

    claims = research_data.get("claims") or []
    if not claims or claims == ["No explicit claims detected."]:
        critiques.append("Claims are not clearly stated or are under-supported.")

    critical_citations = research_data.get("critical_citations") or []
    if not critical_citations:
        critiques.append("Key citations are missing; evidence coverage looks thin.")

    novelty = _infer_novelty(lowered)
    critiques.append(f"Novelty estimate: {novelty}.")

    critique_notes = _format_critique_report(critiques)
    normalized["critique_notes"] = critique_notes

    normalized["logs"].append(
        "Critic Agent: "
        + ("No critical gaps detected." if len(critiques) == 1 else "Gap review completed.")
    )

    return validate_review_state(normalized)


def _infer_novelty(lowered_text: str) -> str:
    if any(keyword in lowered_text for keyword in ["novel", "first", "unprecedented"]):
        return "disruptive"
    if any(keyword in lowered_text for keyword in ["extension", "incremental", "baseline"]):
        return "incremental"
    return "unclear"


def _format_critique_report(points: List[str]) -> str:
    header = "Critical Review Notes"
    body = "\n".join(f"- {normalize_text(point)}" for point in points)
    return f"{header}\n{body}".strip()
