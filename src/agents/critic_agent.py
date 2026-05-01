from __future__ import annotations

import json
import os
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from src.agents.review_prompts import CRITIC_AGENT_PROMPT, ORCHESTRATOR_WORLDVIEW_PROMPT
from src.state import ReviewState, validate_review_state
from src.tools import normalize_text, ollama_chat_structured


class CriticReviewModel(BaseModel):
    """Structured critique output returned by the model-backed critic."""

    model_config = ConfigDict(extra="forbid")

    critique_points: List[str] = Field(default_factory=list)
    novelty: str = ""


def critic_node(state: ReviewState) -> ReviewState:
    """Red-team the manuscript for gaps, logical leaps, and omissions."""
    normalized = validate_review_state(dict(state))
    research_data = normalized.get("research_data", {})

    deterministic_points = _deterministic_critic_points(normalized)
    model_review = CriticReviewModel()
    mode = "deterministic"

    if _use_ollama():
        try:
            model_review = _critic_with_ollama(normalized)
            mode = "ollama"
        except Exception as exc:
            normalized["logs"].append(f"Critic Agent: Ollama fallback triggered ({exc}).")
            mode = "fallback"

    raw_text = normalized.get("raw_text", "")
    lowered = raw_text.lower()

    critiques: List[str] = _merge_unique([*model_review.critique_points, *deterministic_points])

    claims = research_data.get("claims") or []
    if not claims or claims == ["No explicit claims detected."]:
        critiques.append("Claims are not clearly stated or are under-supported.")

    critical_citations = research_data.get("critical_citations") or []
    if not critical_citations:
        critiques.append("Key citations are missing; evidence coverage looks thin.")

    novelty = normalize_text(model_review.novelty) or _infer_novelty(lowered)
    critiques.append(f"Novelty estimate: {novelty}.")

    critique_notes = _format_critique_report(critiques)
    normalized["critique_notes"] = critique_notes

    metadata = normalized["research_data"].setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["critic_mode"] = mode

    normalized["logs"].append(
        "Critic Agent: "
        + (f"{mode} review completed. " if mode != "deterministic" else "")
        + ("No critical gaps detected." if len(critiques) == 1 else "Gap review completed.")
    )

    return validate_review_state(normalized)


def _critic_with_ollama(state: ReviewState) -> CriticReviewModel:
    """Use phi3 to produce a structured critique."""
    ollama_model = os.getenv("CRITIC_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "phi3"))
    ollama_base_url = os.getenv("CRITIC_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    temperature = float(os.getenv("CRITIC_TEMPERATURE", "0"))

    prompt = (
        f"{ORCHESTRATOR_WORLDVIEW_PROMPT}\n\n"
        f"{CRITIC_AGENT_PROMPT}\n\n"
        "Review the manuscript and return JSON only with keys: "
        "critique_points (array of strings) and novelty (string). "
        "Use concise, evidence-based points.\n\n"
        f"Extracted research data: {json.dumps(state.get('research_data', {}), ensure_ascii=False)}\n\n"
        f"Paper text:\n{state.get('raw_text', '')}"
    )

    data = ollama_chat_structured(
        prompt=prompt,
        schema=CriticReviewModel.model_json_schema(),
        model=ollama_model,
        base_url=ollama_base_url,
        temperature=temperature,
    )

    return CriticReviewModel.model_validate(data)


def _deterministic_critic_points(state: ReviewState) -> List[str]:
    """Run the existing local critique checks as a fallback and guardrail."""
    critiques: List[str] = []

    raw_text = state.get("raw_text", "")
    lowered = raw_text.lower()

    if "limitations" not in lowered:
        critiques.append("Limitations are not explicitly discussed.")
    if "ethical" not in lowered and "ethics" not in lowered:
        critiques.append("Ethical considerations are not addressed.")
    if "failure" not in lowered and "robust" not in lowered:
        critiques.append("Failure cases or robustness checks are not described.")

    return critiques


def _use_ollama() -> bool:
    """Return whether the critic should prefer the phi3-backed path."""
    return os.getenv("CRITIC_USE_OLLAMA", "true").lower() == "true"


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
