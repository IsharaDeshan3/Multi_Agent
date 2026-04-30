from __future__ import annotations

from pathlib import Path

import pytest

from src.source_ingestion import resolve_public_paper_source


class _FakeResponse:
    def __init__(self, payload: bytes, url: str, content_type: str) -> None:
        self._payload = payload
        self._url = url
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(payload)),
        }

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]

    def close(self) -> None:
        return None

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def test_resolve_public_paper_source_persists_html_artifact(tmp_path, monkeypatch) -> None:
    html = b"<html><body><h1>Research Question</h1><p>Does the system work?</p></body></html>"
    fake_response = _FakeResponse(html, "https://example.com/paper", "text/html; charset=utf-8")

    monkeypatch.setenv("PAPER_SOURCE_ARTIFACT_ROOT", str(tmp_path / "runs"))
    monkeypatch.setattr("src.source_ingestion.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))])
    monkeypatch.setattr("src.source_ingestion.urlopen", lambda *args, **kwargs: fake_response)

    result = resolve_public_paper_source("https://example.com/paper", run_id="run-123")

    assert result.source_url == "https://example.com/paper"
    assert result.resolved_url == "https://example.com/paper"
    assert "Does the system work?" in result.text
    assert Path(result.artifact_path).exists()
    assert (Path(result.artifact_path) / "extracted.txt").exists()
    assert (Path(result.artifact_path) / "metadata.json").exists()


def test_resolve_public_paper_source_rejects_private_ip() -> None:
    with pytest.raises(ValueError, match="public host or public IP address"):
        resolve_public_paper_source("http://127.0.0.1/paper")


def test_resolve_public_paper_source_normalizes_doi_shortcut(tmp_path, monkeypatch) -> None:
    html = b"<html><body><p>DOI paper text.</p></body></html>"
    fake_response = _FakeResponse(html, "https://doi.org/10.1000/example", "text/html")

    monkeypatch.setenv("PAPER_SOURCE_ARTIFACT_ROOT", str(tmp_path / "runs"))
    monkeypatch.setattr(
        "src.source_ingestion.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    captured_urls: list[str] = []

    def _fake_urlopen(request, timeout=None):
        captured_urls.append(request.full_url)
        return fake_response

    monkeypatch.setattr("src.source_ingestion.urlopen", _fake_urlopen)

    result = resolve_public_paper_source("doi:10.1000/example", run_id="run-456")

    assert captured_urls == ["https://doi.org/10.1000/example"]
    assert result.source_url == "https://doi.org/10.1000/example"
    assert "DOI paper text." in result.text


def test_resolve_public_paper_source_normalizes_arxiv_shortcut(tmp_path, monkeypatch) -> None:
    pdf_payload = b"%PDF-1.4\n%fake"
    fake_response = _FakeResponse(pdf_payload, "https://arxiv.org/pdf/2101.12345v2.pdf", "application/pdf")

    monkeypatch.setenv("PAPER_SOURCE_ARTIFACT_ROOT", str(tmp_path / "runs"))
    monkeypatch.setattr(
        "src.source_ingestion.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    monkeypatch.setattr("src.source_ingestion._extract_pdf_text", lambda payload: "ArXiv paper text.")
    captured_urls: list[str] = []

    def _fake_urlopen(request, timeout=None):
        captured_urls.append(request.full_url)
        return fake_response

    monkeypatch.setattr("src.source_ingestion.urlopen", _fake_urlopen)

    result = resolve_public_paper_source("arXiv:2101.12345v2", run_id="run-789")

    assert captured_urls == ["https://arxiv.org/pdf/2101.12345v2.pdf"]
    assert result.source_url == "https://arxiv.org/pdf/2101.12345v2.pdf"
    assert result.content_type == "application/pdf"
