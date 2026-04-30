import type { RunStatus } from "../lib/types";

type ReportPanelProps = {
  runStatus: RunStatus | null;
};

type ReportSection = {
  title: string;
  body: string;
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

export function ReportPanel({ runStatus }: ReportPanelProps) {
  const report = runStatus?.result_state?.final_feedback ?? null;
  const sections = report ? parseReport(report) : [];
  const recommendation = report ? getRecommendation(report) : "Pending";
  const verdict = report ? getVerdict(report) : "Pending";

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

      {report ? (
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
              <strong>{researchData?.metadata?.mode ?? "-"}</strong>
            </div>
          </div>

          <div className="report-accordion">
            {sections.map((section, index) => (
              <details key={`${section.title}-${index}`} className="report-section" open={index === 0}>
                <summary>
                  <span>{section.title}</span>
                  <span className="report-section-toggle">Toggle</span>
                </summary>
                <pre>{section.body}</pre>
              </details>
            ))}
          </div>
        </div>
      ) : (
        <div className="report-empty">No report available yet.</div>
      )}
    </section>
  );
}