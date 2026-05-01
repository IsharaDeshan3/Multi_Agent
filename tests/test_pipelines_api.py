from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from src.api.server import app


@dataclass
class _FakeSourceResult:
    source_url: str
    resolved_url: str
    content_type: str
    artifact_path: str
    text: str

    def metadata(self) -> dict[str, str]:
        return {
            "source_url": self.source_url,
            "resolved_source_url": self.resolved_url,
            "source_content_type": self.content_type,
            "source_artifact_path": self.artifact_path,
            "source_format": "markdown",
        }


def test_pipeline_run_accepts_paper_url_and_persists_source(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        "src.api.routes.pipelines.resolve_public_paper_source",
        lambda paper_url, run_id=None: _FakeSourceResult(
            source_url=paper_url,
            resolved_url="https://doi.org/10.1000/example",
            content_type="application/pdf",
            artifact_path="logs/runs/run-123/source",
            text="Research Question: Does this pipeline work?\nMethodology: Test harness.",
        ),
    )

    def _fake_background_run(run_id, payload) -> None:
        from src.api.run_status import append_message, update_run

        update_run(
            run_id,
            status="completed",
            current_stage="integrator",
            stage_index=1,
            source_status="fetched",
            source_url=payload.paper_url,
            resolved_source_url="https://doi.org/10.1000/example",
            source_content_type="application/pdf",
            source_format="markdown",
            source_artifact_path="logs/runs/run-123/source",
            result_state={
                "raw_text": "Research Question: Does this pipeline work?\nMethodology: Test harness.",
                "research_data": {
                    "question": "Does this pipeline work?",
                    "methodology": "Test harness.",
                    "claims": ["Methodology is acceptable."],
                    "metadata": {"mode": "deterministic"},
                },
                "audit_results": {"passed": True, "errors": []},
                "critique_notes": "Critical Review Notes\n- Ethics were addressed.",
                "final_report": {
                    "executive_summary": "Structured report assembled.",
                    "recommendation": "Keep",
                    "final_verdict": "Minor Revision",
                    "scorecard": {"novelty": 8, "rigor": 7, "clarity": 10, "narrative": "Hybrid synthesis."},
                    "evidence_log": ["Methodology is acceptable."],
                    "limitations": ["A few limitations remain."],
                    "ethical_considerations": ["Ethics were addressed."],
                    "failure_cases": ["Robustness checks were incomplete."],
                    "source_provenance": {"integrator_mode": "deterministic"},
                    "next_steps": ["Run a final human review."],
                    "markdown": "Review Evaluation File\n\nFinal Verdict:\n- Minor Revision\n",
                },
                "final_feedback": "Review Evaluation File\n\nFinal Verdict:\n- Minor Revision\n",
                "logs": ["Run completed."],
            },
        )
        append_message(run_id, f"Source fetched and stored at logs/runs/run-123/source")
        append_message(run_id, "Run completed.")

    monkeypatch.setattr("src.api.routes.pipelines._run_pipeline_background", _fake_background_run)

    response = client.post(
        "/api/v1/pipelines/review/runs",
        json={"paper_url": "doi:10.1000/example"},
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]

    status_response = client.get(f"/api/v1/pipelines/review/runs/{run_id}")
    status = status_response.json()

    assert status_response.status_code == 200
    assert status["status"] == "completed"
    assert status["source_url"] == "doi:10.1000/example"
    assert status["resolved_source_url"] == "https://doi.org/10.1000/example"
    assert status["source_content_type"] == "application/pdf"
    assert status["source_format"] == "markdown"
    assert status["source_artifact_path"] == "logs/runs/run-123/source"
    assert status["source_status"] == "fetched"
    assert status["result_state"]["final_report"]["recommendation"] == "Keep"
    assert status["result_state"]["final_report"]["scorecard"]["clarity"] == 10
    assert any("Source fetched" in message for message in status["messages"])


def test_pipeline_run_source_endpoint_reports_missing_run() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/pipelines/review/runs/missing-run/source")

    assert response.status_code == 200
    assert response.json()["source_url"] is None
