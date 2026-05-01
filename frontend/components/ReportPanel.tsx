import type { RunStatus } from "../lib/types";

type ReportPanelProps = {
  runStatus: RunStatus | null;
};

type ReportSection = {
  title: string;
  body: string;
};

type KeyValue = {
  key: string;
  value: string;
};

function parseReport(report: string): ReportSection[] {
  const lines = report.split(/\r?\n/);
  const sections: ReportSection[] = [];
  let currentTitle = "Overview";
  let currentBody: string[] = [];

  const pushSection = () => {
    const body = currentBody.join("\n").trim();
    if (body) {
      sections.push({ title: currentTitle, body });
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      currentBody.push("");
      continue;
    }

    const isHeading = !trimmed.startsWith("-") && trimmed.endsWith(":") && trimmed.length < 80;
    if (isHeading) {
      pushSection();
      currentTitle = trimmed.slice(0, -1);
      currentBody = [];
      continue;
    }

    currentBody.push(line);
  }

  pushSection();
  return sections;
}

function getRecommendation(report: string): string {
  const match = report.match(/Recommendation:\s*(.+)/i);
  return match?.[1]?.trim() || "Pending";
}

function getVerdict(report: string): string {
  const match = report.match(/Final Verdict:\s*[\r\n]+-\s*(.+)/i);
  return match?.[1]?.trim() || "Pending";
}

function stringifyValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((entry) => stringifyValue(entry)).join(", ");
  }

  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }

  if (value === null || value === undefined) {
    return "-";
  }

  return String(value);
}

function toLines(items: string[], emptyLabel: string): string {
  return items.length > 0 ? items.map((entry) => `- ${entry}`).join("\n") : `- ${emptyLabel}`;
}

function buildStructuredSections(report: NonNullable<NonNullable<RunStatus["result_state"]>["final_report"]>): ReportSection[] {
  const provenanceEntries: KeyValue[] = Object.entries(report.source_provenance ?? {}).map(([key, value]) => ({
    key,
    value: stringifyValue(value),
  }));

  return [
    {
      title: "Overview",
      body: [
        `Recommendation: ${report.recommendation || "Pending"}`,
        `Final verdict: ${report.final_verdict || "Pending"}`,
      ].join("\n"),
    },
    {
      title: "Executive Summary",
      body: report.executive_summary || "No executive summary was returned.",
    },
    {
      title: "Technical Scorecard",
      body: [
        `- Novelty: ${report.scorecard?.novelty ?? "-"}/10`,
        `- Rigor: ${report.scorecard?.rigor ?? "-"}/10`,
        `- Clarity: ${report.scorecard?.clarity ?? "-"}/10`,
        `- Narrative: ${report.scorecard?.narrative || "Not provided."}`,
      ].join("\n"),
    },
    {
      title: "Evidence Log",
      body: toLines(report.evidence_log ?? [], "No evidence items were returned."),
    },
    {
      title: "Limitations / Risks",
      body: toLines(report.limitations ?? [], "No limitations were returned."),
    },
    {
      title: "Ethical Considerations",
      body: toLines(report.ethical_considerations ?? [], "No ethical considerations were returned."),
    },
    {
      title: "Failure Cases / Robustness Checks",
      body: toLines(report.failure_cases ?? [], "No failure cases were returned."),
    },
    {
      title: "Next Steps",
      body: toLines(report.next_steps ?? [], "No next steps were returned."),
    },
    {
      title: "Source Provenance",
      body: provenanceEntries.length
        ? provenanceEntries.map(({ key, value }) => `- ${key}: ${value}`).join("\n")
        : "- No provenance metadata was returned.",
    },
  ];
}

export function ReportPanel({ runStatus }: ReportPanelProps) {
  const structuredReport = runStatus?.result_state?.final_report ?? null;
  const report = structuredReport?.markdown ?? runStatus?.result_state?.final_feedback ?? null;
  const sections = structuredReport ? buildStructuredSections(structuredReport) : report ? parseReport(report) : [];
  const recommendation = structuredReport?.recommendation ?? (report ? getRecommendation(report) : "Pending");
  const verdict = structuredReport?.final_verdict ?? (report ? getVerdict(report) : "Pending");

  const researchData = runStatus?.result_state?.research_data as
    | Record<string, any>
    | undefined;
  const confidence = researchData?.extraction_confidence;
  const sourceCount = Array.isArray(researchData?.metadata?.sources)
    ? researchData.metadata.sources.length
    : 0;

  return (
    <section className="panel report-panel">
      <div className="report-header">
        <div>
          <p className="kicker report-kicker">Paper report</p>
          <h2>Final Evaluation</h2>
          <p className="meta report-intro">
            {runStatus?.status === "completed"
              ? report
                ? "The integrator has finished and the final evaluation is ready below."
                : "The run finished, but no report text was returned from the pipeline."
              : runStatus
                ? "The report will appear here once the pipeline reaches its final stage."
                : "Launch a run to generate the report."}
          </p>
        </div>
        <div className="report-status-stack">
          <div className="report-status-card">
            <span className="report-status-label">Recommendation</span>
            <strong>{recommendation}</strong>
          </div>
          <div className="report-status-card report-status-card-accent">
            <span className="report-status-label">Final verdict</span>
            <strong>{verdict}</strong>
          </div>
          <div className="report-status-meta">
            <span>Confidence {confidence ? `${confidence}/10` : "-"}</span>
            <span>{sourceCount ? `${sourceCount} source${sourceCount === 1 ? "" : "s"}` : "No source metadata"}</span>
          </div>
        </div>
      </div>

      {runStatus?.status === "failed" ? (
        <div className="report-error">
          {runStatus.error ?? "Model not available. Enable Ollama and pull the requested model before running the parser."}
        </div>
      ) : sections.length > 0 ? (
        <div className="report-body">
          <div className="report-highlight-row">
            <div className="report-highlight">
              <span>Report status</span>
              <strong>Completed</strong>
            </div>
            <div className="report-highlight">
              <span>Sections</span>
              <strong>{sections.length}</strong>
            </div>
            <div className="report-highlight">
              <span>Mode</span>
              <strong>{structuredReport ? "structured" : researchData?.metadata?.mode ?? "-"}</strong>
            </div>
          </div>

          <article className="report-document">
            {sections.map((section, index) => (
              <section key={`${section.title}-${index}`} className="report-section-card">
                <h3>{section.title}</h3>
                <pre>{section.body}</pre>
              </section>
            ))}
          </article>
        </div>
      ) : (
        <div className="report-empty">No report available yet.</div>
      )}
    </section>
  );
}