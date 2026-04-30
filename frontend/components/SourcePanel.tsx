import type { RunStatus } from "../lib/types";

type SourcePanelProps = {
  runStatus: RunStatus | null;
};

export function SourcePanel({ runStatus }: SourcePanelProps) {
  const statusClass =
    runStatus?.source_status === "failed"
      ? "error"
      : runStatus?.source_status === "fetched"
        ? "ok"
        : "";

  return (
    <section className="panel">
      <h2>Paper Source</h2>
      <div className={`status-pill ${statusClass}`}>
        <span />
        {runStatus?.source_status ?? "Idle"}
      </div>
      <p className="meta">Input URL: {runStatus?.source_url ?? "-"}</p>
      <p className="meta">
        Resolved URL: {runStatus?.resolved_source_url ?? "-"}
      </p>
      <p className="meta">
        Content type: {runStatus?.source_content_type ?? "-"}
      </p>
      <p className="meta">
        Artifact path: {runStatus?.source_artifact_path ?? "-"}
      </p>
    </section>
  );
}
