from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.tools import normalize_markdown_text, normalize_text

DEFAULT_MAX_SOURCE_BYTES = int(os.getenv("PAPER_SOURCE_MAX_BYTES", str(5 * 1024 * 1024)))
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("PAPER_SOURCE_TIMEOUT_SECONDS", "20"))
DEFAULT_ARTIFACT_ROOT = Path("logs/runs")
DEFAULT_MIN_REQUEST_DELAY_SECONDS = float(os.getenv("PAPER_SOURCE_MIN_REQUEST_DELAY_SECONDS", "0"))

_FETCH_LOCK = Lock()
_LAST_FETCH_AT = 0.0


def _artifact_root() -> Path:
    """Resolve the artifact root at call time so tests can override it."""
    return Path(os.getenv("PAPER_SOURCE_ARTIFACT_ROOT", str(DEFAULT_ARTIFACT_ROOT)))


@dataclass
class PaperSourceResult:
    """Resolved and persisted paper-source payload."""

    source_url: str
    resolved_url: str
    content_type: str
    artifact_path: str
    text: str

    def metadata(self) -> Dict[str, Any]:
        """Return serializable source metadata for run state and logs."""
        return {
            "source_url": self.source_url,
            "resolved_source_url": self.resolved_url,
            "source_content_type": self.content_type,
            "source_artifact_path": self.artifact_path,
            "source_format": "markdown",
        }


class _HTMLTextExtractor(HTMLParser):
    """Extract readable text from HTML without external dependencies."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self._chunks.append(cleaned)

    def get_text(self) -> str:
        return normalize_text("\n".join(self._chunks))


def resolve_public_paper_source(
    source_url: str,
    *,
    run_id: Optional[str] = None,
    artifact_root: Optional[Path] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
) -> PaperSourceResult:
    """Fetch, validate, extract, and persist a public paper source.

    Args:
        source_url: Public paper URL to ingest.
        run_id: Optional pipeline run id used for artifact persistence.
        artifact_root: Optional override for artifact storage root.
        timeout_seconds: Network timeout in seconds.
        max_bytes: Maximum allowed remote payload size.

    Returns:
        PaperSourceResult: Normalized text and persistence metadata.

    Raises:
        ValueError: If the URL is invalid or resolves to a non-public host.
        RuntimeError: If fetching, extraction, or persistence fails.
    """
    validated_url = _normalize_public_paper_source_url(source_url)
    validated_url = _validate_public_http_url(validated_url)
    response = _open_validated_url(validated_url, timeout_seconds=timeout_seconds, max_bytes=max_bytes)

    try:
        resolved_url = response.geturl()
        _ensure_public_destination(resolved_url)
        content_type = _normalize_content_type(response.headers.get("Content-Type"))
        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise RuntimeError(f"Remote source exceeds the {max_bytes} byte limit.")
    finally:
        response.close()

    text = _extract_source_text(payload, resolved_url=resolved_url, content_type=content_type)
    markdown_text = normalize_markdown_text(text)
    artifact_path = _persist_source_artifact(
        source_url=validated_url,
        resolved_url=resolved_url,
        content_type=content_type,
        text=markdown_text,
        payload=payload,
        run_id=run_id,
        artifact_root=artifact_root,
    )

    return PaperSourceResult(
        source_url=validated_url,
        resolved_url=resolved_url,
        content_type=content_type,
        artifact_path=str(artifact_path),
        text=markdown_text,
    )


def _normalize_public_paper_source_url(source_url: str) -> str:
    """Normalize DOI and arXiv shorthand into fetchable HTTP URLs."""
    candidate = source_url.strip()
    lowered = candidate.lower()

    if lowered.startswith("doi:"):
        return f"https://doi.org/{candidate.split(':', 1)[1].strip()}"

    if lowered.startswith("arxiv:"):
        return _normalize_arxiv_identifier(candidate.split(':', 1)[1].strip())

    if _looks_like_bare_doi(candidate):
        return f"https://doi.org/{candidate}"

    if _looks_like_bare_arxiv_identifier(candidate):
        return _normalize_arxiv_identifier(candidate)

    parsed = urlparse(candidate)
    if parsed.netloc.lower() in {"doi.org", "dx.doi.org"} and parsed.path.strip("/"):
        return f"https://doi.org/{parsed.path.strip('/')}"

    if parsed.netloc.lower() == "arxiv.org":
        normalized = _normalize_arxiv_url(candidate)
        if normalized:
            return normalized

    return candidate


def _validate_public_http_url(source_url: str) -> str:
    """Validate that a URL is HTTP(S) and points to a public destination."""
    parsed = urlparse(source_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("paper_url must use http or https.")
    if not parsed.netloc:
        raise ValueError("paper_url must include a host.")

    _ensure_public_host(parsed.hostname)
    return parsed.geturl()


def _looks_like_bare_doi(source_url: str) -> bool:
    """Detect DOI strings supplied without a scheme."""
    return bool(re.match(r"^10\.\d{4,9}/\S+$", source_url.strip(), flags=re.IGNORECASE))


def _looks_like_bare_arxiv_identifier(source_url: str) -> bool:
    """Detect arXiv identifiers supplied without a scheme."""
    return bool(re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", source_url.strip(), flags=re.IGNORECASE))


def _normalize_arxiv_identifier(identifier: str) -> str:
    """Normalize an arXiv identifier into a direct PDF URL."""
    stripped = identifier.strip()
    match = re.match(r"^(?P<id>\d{4}\.\d{4,5})(?P<version>v\d+)?$", stripped, flags=re.IGNORECASE)
    if match:
        arxiv_id = match.group("id") + (match.group("version") or "")
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    return stripped


def _normalize_arxiv_url(source_url: str) -> str:
    """Convert common arXiv URLs into a direct PDF fetch URL."""
    parsed = urlparse(source_url.strip())
    path = parsed.path.strip("/")
    if not path:
        return source_url

    parts = path.split("/")
    if len(parts) >= 2 and parts[0] in {"abs", "pdf"}:
        arxiv_id = parts[1]
        if parts[0] == "pdf" and arxiv_id.endswith(".pdf"):
            arxiv_id = arxiv_id[:-4]
        if not arxiv_id.endswith(".pdf"):
            arxiv_id = f"{arxiv_id}.pdf"
        if not arxiv_id.startswith("http"):
            return f"https://arxiv.org/pdf/{arxiv_id}"

    return source_url


def _open_validated_url(source_url: str, *, timeout_seconds: int, max_bytes: int):
    """Open a validated URL with a paper-friendly request header set."""
    if DEFAULT_MIN_REQUEST_DELAY_SECONDS > 0:
        global _LAST_FETCH_AT
        with _FETCH_LOCK:
            elapsed = time.monotonic() - _LAST_FETCH_AT
            if elapsed < DEFAULT_MIN_REQUEST_DELAY_SECONDS:
                time.sleep(DEFAULT_MIN_REQUEST_DELAY_SECONDS - elapsed)
            _LAST_FETCH_AT = time.monotonic()

    request = Request(
        source_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Multi-Agent Research Review/1.0)",
            "Accept": "application/pdf,text/html,application/xhtml+xml,text/plain;q=0.8,*/*;q=0.5",
        },
        method="GET",
    )

    try:
        response = urlopen(request, timeout=timeout_seconds)
    except URLError as exc:
        raise RuntimeError(f"Failed to fetch paper source: {exc}") from exc

    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > max_bytes:
        response.close()
        raise RuntimeError(f"Remote source exceeds the {max_bytes} byte limit.")

    return response


def _ensure_public_destination(source_url: str) -> None:
    """Re-check the final destination after redirects."""
    parsed = urlparse(source_url)
    _ensure_public_host(parsed.hostname)


def _ensure_public_host(hostname: Optional[str]) -> None:
    """Reject localhost and private-network destinations."""
    if not hostname:
        raise ValueError("paper_url must include a host.")

    lowered = hostname.lower()
    if lowered in {"localhost", "0.0.0.0"} or lowered.endswith(".local"):
        raise ValueError("paper_url must resolve to a public host.")

    try:
        resolved_addresses = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise ValueError(f"paper_url host could not be resolved: {hostname}") from exc

    public_address_found = False
    for entry in resolved_addresses:
        address = entry[4][0]
        try:
            ip_address = ipaddress.ip_address(address)
        except ValueError:
            continue

        if ip_address.is_private or ip_address.is_loopback or ip_address.is_link_local:
            continue
        if ip_address.is_multicast or ip_address.is_reserved or ip_address.is_unspecified:
            continue
        public_address_found = True
        break

    if not public_address_found:
        raise ValueError("paper_url must resolve to a public host or public IP address.")


def _normalize_content_type(content_type: Optional[str]) -> str:
    """Return the MIME type without charset or parameters."""
    if not content_type:
        return "application/octet-stream"
    return content_type.split(";", 1)[0].strip().lower()


def _extract_source_text(payload: bytes, *, resolved_url: str, content_type: str) -> str:
    """Extract text from a fetched source using MIME type and URL hints."""
    url_suffix = Path(urlparse(resolved_url).path).suffix.lower()

    if content_type == "application/pdf" or url_suffix == ".pdf":
        return _extract_pdf_text(payload)

    if content_type in {"text/html", "application/xhtml+xml"} or url_suffix in {".html", ".htm"}:
        return _extract_html_text(payload)

    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        decoded = payload.decode("latin-1", errors="ignore")

    if "<html" in decoded.lower() or "<body" in decoded.lower():
        return _extract_html_text(payload)

    return normalize_text(decoded)


def _extract_pdf_text(payload: bytes) -> str:
    """Extract text from a PDF payload."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("PDF source extraction requires the 'pypdf' package.") from exc

    reader = PdfReader(BytesIO(payload))
    pages = [page.extract_text() or "" for page in reader.pages]
    return normalize_text("\n".join(pages))


def _extract_html_text(payload: bytes) -> str:
    """Extract text from an HTML payload."""
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        decoded = payload.decode("latin-1", errors="ignore")

    parser = _HTMLTextExtractor()
    parser.feed(decoded)
    parser.close()
    return parser.get_text()


def _persist_source_artifact(
    *,
    source_url: str,
    resolved_url: str,
    content_type: str,
    text: str,
    payload: bytes,
    run_id: Optional[str],
    artifact_root: Optional[Path],
) -> Path:
    """Persist the raw payload, extracted text, and metadata for a run."""
    root = artifact_root or _artifact_root()
    run_folder = root / (run_id or "ad-hoc") / "source"
    run_folder.mkdir(parents=True, exist_ok=True)

    suffix = _artifact_suffix(content_type)
    raw_path = run_folder / f"source{suffix}"
    text_path = run_folder / "extracted.txt"
    markdown_path = run_folder / "extracted.md"
    metadata_path = run_folder / "metadata.json"

    raw_path.write_bytes(payload)
    text_path.write_text(text, encoding="utf-8")
    markdown_path.write_text(text, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "source_url": source_url,
                "resolved_source_url": resolved_url,
                "content_type": content_type,
                "raw_path": str(raw_path),
                "text_path": str(text_path),
                "markdown_path": str(markdown_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return run_folder


def _artifact_suffix(content_type: str) -> str:
    """Choose a stable artifact suffix from the content type."""
    if content_type == "application/pdf":
        return ".pdf"
    if content_type in {"text/html", "application/xhtml+xml"}:
        return ".html"
    if content_type.startswith("text/"):
        return ".txt"
    return ".bin"
