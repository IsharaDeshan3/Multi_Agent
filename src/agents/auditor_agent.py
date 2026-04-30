from __future__ import annotations

import re
from typing import List

from src.state import ReviewState, validate_review_state
from src.tools import normalize_text


def auditor_node(state: ReviewState) -> ReviewState:
    """Audit methodology and data integrity signals.

    The auditor performs deterministic checks on the extracted methodology,
    claims, and metric usage. It records any violations in audit_results.
    """
    normalized = validate_review_state(dict(state))
    research_data = normalized.get("research_data", {})

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

    metrics = _extract_metrics(normalized.get("raw_text", ""))
    if not metrics:
        errors.append("No standard evaluation metrics detected in the manuscript.")

    normalized["audit_results"] = {
        "passed": len(errors) == 0,
        "errors": errors,
    }

    normalized["logs"].append(
        "Auditor Agent: "
        + ("All checks passed." if not errors else f"Found {len(errors)} issue(s).")
    )

    return validate_review_state(normalized)


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
