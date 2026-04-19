from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib import request
from urllib.error import URLError


def read_paper_file(file_path: str) -> str:
    """Read a local text or markdown file for review.

    Args:
        file_path: Local path to the source document.

    Returns:
        str: Full file contents.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be read.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found.")

    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def extract_research_data(raw_text: str) -> Dict[str, Any]:
    """Extract research question, methodology, and claims from text.

    This deterministic parser keeps tests stable and acts as a fallback
    when local model inference is unavailable.

    Args:
        raw_text: Source paper text.

    Returns:
        Dict[str, Any]: Structured research data.
    """
    question = _extract_prefixed_value(raw_text, ["research question", "question"])
    methodology = _extract_prefixed_value(raw_text, ["methodology", "method"])
    claims = _extract_claims(raw_text)

    if not question:
        question = _first_sentence(raw_text)
    if not methodology:
        methodology = "Methodology not explicitly identified."
    if not claims:
        claims = ["No explicit claims detected."]

    return {
        "question": question,
        "methodology": methodology,
        "claims": claims,
    }


def ollama_generate(
    prompt: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: int = 60,
) -> str:
    """Generate text from a local Ollama model.

    Args:
        prompt: Prompt sent to the model.
        model: Optional model name override.
        base_url: Optional Ollama base URL override.
        timeout_seconds: Request timeout in seconds.

    Returns:
        str: Model response text.

    Raises:
        RuntimeError: If Ollama request fails.
    """
    resolved_model = model or os.getenv("OLLAMA_MODEL", "llama3.1")
    resolved_base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    endpoint = f"{resolved_base_url.rstrip('/')}/api/generate"

    payload = {
        "model": resolved_model,
        "prompt": prompt,
        "stream": False,
    }

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Failed to connect to Ollama at {endpoint}: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    return str(data.get("response", "")).strip()


def _extract_prefixed_value(raw_text: str, prefixes: List[str]) -> str:
    """Extract value from lines like 'Prefix: value'."""
    pattern = re.compile(r"^\s*([A-Za-z ]+)\s*:\s*(.+?)\s*$", re.IGNORECASE)
    for line in raw_text.splitlines():
        match = pattern.match(line)
        if not match:
            continue

        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if key in prefixes and value:
            return value

    return ""


def _extract_claims(raw_text: str) -> List[str]:
    """Extract claim-like bullet or numbered list lines."""
    claims: List[str] = []
    for line in raw_text.splitlines():
        normalized = line.strip()
        if not normalized:
            continue

        if normalized.startswith("-"):
            claims.append(normalized.lstrip("- ").strip())
            continue

        if re.match(r"^\d+[\.)]\s+", normalized):
            claims.append(re.sub(r"^\d+[\.)]\s+", "", normalized).strip())
            continue

        if normalized.lower().startswith("claim") and ":" in normalized:
            claims.append(normalized.split(":", 1)[1].strip())

    return claims


def _first_sentence(raw_text: str) -> str:
    """Return the first non-empty sentence-like segment from text."""
    compact = " ".join(raw_text.split())
    if not compact:
        return ""

    parts = re.split(r"(?<=[.!?])\s+", compact)
    return parts[0].strip() if parts else compact
