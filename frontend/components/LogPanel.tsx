import type { RunStatus } from "../lib/types";

type LogPanelProps = {
  runStatus: RunStatus | null;
  error: string | null;
};

export function LogPanel({ runStatus, error }: LogPanelProps) {
  const messages = runStatus?.messages ?? [];
  const result = runStatus?.result_state;

  return (
    <section className="panel">
      <h2>Run Console</h2>
      <p className="meta">Run id: {runStatus?.run_id ?? "-"}</p>
      <p className="meta">Status: {runStatus?.status ?? "idle"}</p>
      {error ? <div className="log-item error">{error}</div> : null}
      {runStatus?.error ? (
        <div className="log-item error">{runStatus.error}</div>
      ) : null}
      <div className="log-list">
        {messages.length === 0 ? (
          <div className="log-item">No run messages yet.</div>
        ) : (
          messages.map((entry, index) => (
            <div key={`${entry}-${index}`} className="log-item">
              {entry}
            </div>
          ))
        )}
      </div>
      {result ? (
        <div className="meta">
          Latest question: {String(result.research_data?.question ?? "-")}
        </div>
      ) : null}
    </section>
  );
}
