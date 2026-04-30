from __future__ import annotations

import json
import os
import re
from pathlib import Path
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


def read_document_file(file_path: str) -> str:
    """Read a supported local document file for review.

    Args:
        file_path: Local path to the source document.

    Returns:
        str: Full file contents.

    Raises:
        FileNotFoundError: If the file does not exist.
        RuntimeError: If a supported binary format requires an unavailable dependency.
        OSError: If the file cannot be read.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".rst", ""}:
        return read_paper_file(file_path)

    if suffix == ".pdf":
        return _read_pdf_file(file_path)

    if suffix == ".docx":
        return _read_docx_file(file_path)

    return read_paper_file(file_path)


def extract_research_data(raw_text: str) -> Dict[str, Any]:
    """Extract research question, methodology, and claims from text.

    This deterministic parser keeps tests stable and acts as a fallback
    when local model inference is unavailable.

    Args:
        raw_text: Source paper text.

    Returns:
        Dict[str, Any]: Structured research data.
    """
    question = _extract_prefixed_value(
        raw_text,
        ["research question", "question", "objective", "aim"],
    )
    methodology = _extract_prefixed_value(raw_text, ["methodology", "method", "methods"])
    sections = _extract_sections(raw_text)

    if not question:
        question = _infer_question_from_sections(sections)
    if not methodology:
        methodology = _infer_methodology_from_sections(sections)

    claims = _extract_claims(raw_text)
    claims.extend(_extract_claim_sentences(sections.get("abstract", "")))
    claims.extend(_extract_claim_sentences(sections.get("conclusion", "")))
    claims.extend(_extract_claim_sentences(sections.get("discussion", "")))
    claims = _deduplicate_preserve_order(claims)

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


def normalize_text(raw_text: str) -> str:
    """Normalize whitespace and light punctuation spacing without changing meaning."""
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines: List[str] = []

    for line in normalized.split("\n"):
        cleaned = re.sub(r"\s+", " ", line).strip()
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        cleaned = re.sub(r"([,.;:!?])(\w)", r"\1 \2", cleaned)
        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines).strip()


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


def ollama_chat_structured(
    prompt: str,
    schema: Dict[str, Any],
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: int = 60,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """Generate a structured JSON response from Ollama chat.

    Args:
        prompt: Prompt sent to the model.
        schema: JSON schema used to constrain the response.
        model: Optional model name override.
        base_url: Optional Ollama base URL override.
        timeout_seconds: Request timeout in seconds.
        temperature: Sampling temperature, defaulting to zero for stability.

    Returns:
        Dict[str, Any]: Parsed JSON response content.

    Raises:
        RuntimeError: If Ollama request fails or returns invalid structured content.
    """
    resolved_model = model or os.getenv("PARSER_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "phi3"))
    resolved_base_url = base_url or os.getenv(
        "PARSER_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    endpoint = f"{resolved_base_url.rstrip('/')}/api/chat"

    payload = {
        "model": resolved_model,
        "messages": [{"role": "user", "content": prompt}],
        "format": schema,
        "stream": False,
        "options": {"temperature": temperature},
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

    message = data.get("message", {})
    content = str(message.get("content", "")).strip()
    if not content:
        raise RuntimeError("Ollama structured response did not include message content.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama structured response was not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Ollama structured response must be a JSON object.")

    return parsed


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


def _extract_sections(raw_text: str) -> Dict[str, str]:
    """Extract simple heading-based sections from a paper-like document."""
    heading_aliases = {
        "abstract": "abstract",
        "research question": "research question",
        "question": "research question",
        "objective": "research question",
        "aim": "research question",
        "methodology": "methodology",
        "methods": "methodology",
        "method": "methodology",
        "results": "results",
        "discussion": "discussion",
        "conclusion": "conclusion",
        "limitations": "limitations",
    }

    sections: Dict[str, List[str]] = {}
    current_section: Optional[str] = None

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        heading = stripped.lower().rstrip(":")
        if heading in heading_aliases and len(heading.split()) <= 3:
            current_section = heading_aliases[heading]
            sections.setdefault(current_section, [])
            continue

        if current_section:
            sections.setdefault(current_section, []).append(stripped)

    return {name: " ".join(lines).strip() for name, lines in sections.items() if lines}


def _infer_question_from_sections(sections: Dict[str, str]) -> str:
    """Infer the research question from explicit or nearby section text."""
    candidate_sections = [sections.get("research question", ""), sections.get("abstract", "")]
    for section in candidate_sections:
        if section:
            sentence = _first_sentence(section)
            if sentence:
                return sentence
    return ""


def _infer_methodology_from_sections(sections: Dict[str, str]) -> str:
    """Infer methodology text from methods or abstract sections."""
    candidate_sections = [sections.get("methodology", ""), sections.get("abstract", "")]
    for section in candidate_sections:
        if section:
            sentence = _first_sentence(section)
            if sentence:
                return sentence
    return ""


def _extract_claim_sentences(section_text: str) -> List[str]:
    """Extract assertive claim-like sentences from a section."""
    if not section_text:
        return []

    claims: List[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", section_text):
        cleaned = sentence.strip()
        if not cleaned:
            continue

        lowered = cleaned.lower()
        if any(keyword in lowered for keyword in ["we find", "we found", "we show", "our results", "suggest", "indicate", "demonstrate"]):
            claims.append(cleaned)

    return claims


def _deduplicate_preserve_order(items: List[str]) -> List[str]:
    """Remove duplicate strings while preserving the first occurrence order."""
    seen = set()
    deduplicated: List[str] = []

    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduplicated.append(normalized)

    return deduplicated


def _read_pdf_file(file_path: str) -> str:
    """Read text from a PDF file when the optional dependency is installed."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("PDF support requires the 'pypdf' package.") from exc

    reader = PdfReader(file_path)
    pages: List[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return normalize_text("\n".join(pages))


def _read_docx_file(file_path: str) -> str:
    """Read text from a DOCX file when the optional dependency is installed."""
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("DOCX support requires the 'python-docx' package.") from exc

    document = Document(file_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return normalize_text("\n".join(paragraphs))


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
