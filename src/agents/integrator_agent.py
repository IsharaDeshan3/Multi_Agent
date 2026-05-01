from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List

from pydantic import BaseModel, ConfigDict

from src.agents.review_prompts import ORCHESTRATOR_WORLDVIEW_PROMPT, SYNTHESIZER_AGENT_PROMPT
from src.state import (
    FinalReportModel,
    FinalReportScorecardModel,
    ReviewState,
    validate_review_state,
)
from src.tools import normalize_text, ollama_chat_structured


class IntegratorReviewModel(BaseModel):
    """Structured synthesis output returned by the model-backed integrator."""

    model_config = ConfigDict(extra="forbid")

    final_report: FinalReportModel = FinalReportModel()


def integrator_node(state: ReviewState) -> ReviewState:
    """Synthesize the full review into a structured report."""
    normalized = validate_review_state(dict(state))
    research_data = normalized.get("research_data", {})
    audit_results = normalized.get("audit_results", {})
    critique_notes = normalized.get("critique_notes", "")

    deterministic_report = _build_deterministic_report(research_data, audit_results, critique_notes)
    model_review = IntegratorReviewModel()
    mode = "deterministic"

    if _use_ollama():
        try:
            model_review = _integrate_with_ollama(normalized)
            mode = "ollama"
        except Exception as exc:
            normalized["logs"].append(f"Integrator Agent: Ollama fallback triggered ({exc}).")
            mode = "fallback"

    final_report = _merge_reports(deterministic_report, model_review.final_report)
    final_report.source_provenance = _build_source_provenance(research_data, mode)
    final_feedback = final_report.markdown or _render_report_markdown(final_report)
    final_report.markdown = final_feedback

    metadata = normalized["research_data"].setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["integrator_mode"] = mode

    normalized["final_report"] = final_report.model_dump()
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
        "Synthesize a final review report and return JSON only with key final_report. "
        "The final_report must include executive_summary, recommendation, final_verdict, scorecard, "
        "evidence_log, limitations, ethical_considerations, failure_cases, source_provenance, next_steps, "
        "and markdown. Use the audit results, critique notes, and parser metadata to generate a concise but complete report.\n\n"
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


def _build_deterministic_report(research_data, audit_results, critique_notes: str) -> FinalReportModel:
    """Build the structured deterministic synthesis report."""
    passed = bool(audit_results.get("passed"))
    errors = audit_results.get("errors", []) or []

    extraction_confidence = int(research_data.get("extraction_confidence", 0) or 0)
    novelty_score = _score_novelty(critique_notes)
    rigor_score = 8 if passed else max(3, 8 - len(errors) * 2)
    clarity_score = max(3, min(10, 4 + extraction_confidence))

    keep_recommendation = "Keep" if passed and extraction_confidence >= 6 else "Discard"
    verdict = _final_verdict(passed, len(errors), critique_notes)

    evidence_log = _build_evidence_log(errors, critique_notes)
    limitations = _extract_critique_notes(critique_notes, ["limit", "limitation", "constraint", "scope"])
    ethical_considerations = _extract_critique_notes(critique_notes, ["ethic", "bias", "fairness", "responsible"])
    failure_cases = _extract_critique_notes(critique_notes, ["failure", "robust", "edge case", "stress", "adversarial"])

    if not limitations:
        limitations = ["The review did not explicitly describe limitations."]
    if not ethical_considerations:
        ethical_considerations = ["Ethical considerations were not explicitly discussed."]
    if not failure_cases:
        failure_cases = ["Failure cases and robustness checks were not explicitly described."]

    next_steps = _build_next_steps(passed, errors, extraction_confidence)

    report = FinalReportModel(
        executive_summary=_build_executive_summary(keep_recommendation, verdict, errors, extraction_confidence),
        recommendation=keep_recommendation,
        final_verdict=verdict,
        scorecard=FinalReportScorecardModel(
            novelty=novelty_score,
            rigor=rigor_score,
            clarity=clarity_score,
            narrative=_build_scorecard_narrative(keep_recommendation, novelty_score, rigor_score, clarity_score),
        ),
        evidence_log=evidence_log,
        limitations=limitations,
        ethical_considerations=ethical_considerations,
        failure_cases=failure_cases,
        next_steps=next_steps,
    )
    report.markdown = _render_report_markdown(report)
    return report


def _merge_reports(base_report: FinalReportModel, model_report: FinalReportModel) -> FinalReportModel:
    """Overlay a model report on top of the deterministic baseline."""
    base_data = base_report.model_dump()
    override_data = model_report.model_dump()

    merged = dict(base_data)
    for key, value in override_data.items():
        if key == "scorecard" and isinstance(value, dict):
            merged_scorecard = dict(base_data["scorecard"])
            for score_key, score_value in value.items():
                if score_value not in (None, "", [], {}, 0):
                    merged_scorecard[score_key] = score_value
            merged["scorecard"] = merged_scorecard
            continue

        if value not in (None, "", [], {}):
            merged[key] = value

    return FinalReportModel.model_validate(merged)


def _build_source_provenance(research_data: Dict[str, Any], mode: str) -> Dict[str, Any]:
    metadata = research_data.get("metadata", {}) if isinstance(research_data, dict) else {}
    provenance = {
        "parser_mode": metadata.get("mode"),
        "auditor_mode": metadata.get("auditor_mode"),
        "critic_mode": metadata.get("critic_mode"),
        "integrator_mode": mode,
        "source_url": metadata.get("source_url"),
        "resolved_source_url": metadata.get("resolved_source_url"),
        "source_content_type": metadata.get("source_content_type"),
        "source_format": metadata.get("source_format"),
        "source_artifact_path": metadata.get("source_artifact_path"),
        "agents": ["parser", "auditor", "critic", "integrator"],
    }
    return {key: value for key, value in provenance.items() if value not in (None, "", [], {})}


def _merge_unique(items: Iterable[str]) -> List[str]:
    """Deduplicate strings while preserving order."""
    seen = set()
    merged: List[str] = []
    for item in items:
        cleaned = normalize_text(str(item))
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        merged.append(cleaned)
    return merged


def _build_executive_summary(recommendation: str, verdict: str, errors: List[str], extraction_confidence: int) -> str:
    issue_count = len(errors)
    confidence_clause = "high" if extraction_confidence >= 7 else "moderate" if extraction_confidence >= 4 else "low"
    return (
        f"The integrated review recommends {recommendation.lower()} with a {confidence_clause} extraction confidence. "
        f"The final verdict is {verdict.lower()} based on {issue_count} identified issue(s)."
    )


def _build_scorecard_narrative(recommendation: str, novelty: int, rigor: int, clarity: int) -> str:
    return (
        f"Recommendation: {recommendation}. "
        f"Novelty is rated at {novelty}/10, rigor at {rigor}/10, and clarity at {clarity}/10."
    )


def _build_next_steps(passed: bool, errors: List[str], extraction_confidence: int) -> List[str]:
    next_steps: List[str] = []
    if not passed:
        next_steps.append("Address the flagged methodology and reporting gaps before resubmission.")
    if extraction_confidence < 6:
        next_steps.append("Improve source extraction quality or provide a cleaner paper source.")
    if not errors:
        next_steps.append("Consider a lightweight human review before final acceptance.")
    return next_steps or ["Proceed with the current manuscript and monitor reviewer feedback."]


def _extract_critique_notes(critique_notes: str, keywords: List[str]) -> List[str]:
    matches: List[str] = []
    for line in critique_notes.splitlines():
        cleaned = line.strip().lstrip("- ").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if any(keyword in lowered for keyword in keywords):
            matches.append(cleaned)
    return _merge_unique(matches)


def _render_report_markdown(report: FinalReportModel) -> str:
    evidence_lines = [f"- {normalize_text(entry)}" for entry in report.evidence_log]
    if not evidence_lines:
        evidence_lines = ["- No critical issues logged."]

    lines = [
        "Review Evaluation File",
        "",
        "Executive Summary:",
        f"- Recommendation: {report.recommendation}",
        f"- {normalize_text(report.executive_summary)}",
        "",
        "Technical Scorecard:",
        f"- Novelty: {report.scorecard.novelty}/10",
        f"- Rigor: {report.scorecard.rigor}/10",
        f"- Clarity: {report.scorecard.clarity}/10",
        f"- Narrative: {normalize_text(report.scorecard.narrative)}",
        "",
        "Evidence Log:",
        *evidence_lines,
        "",
        "Limitations / Risks:",
        *[f"- {normalize_text(entry)}" for entry in report.limitations],
        "",
        "Ethical Considerations:",
        *[f"- {normalize_text(entry)}" for entry in report.ethical_considerations],
        "",
        "Failure Cases / Robustness Checks:",
        *[f"- {normalize_text(entry)}" for entry in report.failure_cases],
        "",
        "Next Steps:",
        *[f"- {normalize_text(entry)}" for entry in report.next_steps],
        "",
        "Source Provenance:",
    ]

    provenance_lines = [f"- {key}: {value}" for key, value in report.source_provenance.items()]
    if not provenance_lines:
        provenance_lines = ["- No provenance recorded."]

    lines.extend(provenance_lines)
    lines.extend([
        "",
        "Final Verdict:",
        f"- {report.final_verdict}",
    ])
    return "\n".join(lines)


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


def _build_evidence_log(errors: list[str], critique_notes: str) -> List[str]:
    entries = [normalize_text(error) for error in errors]
    critique_lines = [
        line.strip().lstrip("- ").strip()
        for line in critique_notes.splitlines()
        if line.strip().startswith("-")
    ]
    entries.extend([normalize_text(line) for line in critique_lines[:3] if normalize_text(line)])
    return _merge_unique(entries) if entries else ["No critical issues logged."]
