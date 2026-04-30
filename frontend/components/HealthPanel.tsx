import type { HealthResponse } from "../lib/types";

type HealthPanelProps = {
  health: HealthResponse | null;
  error: string | null;
  lastUpdated: string | null;
};

export function HealthPanel({ health, error, lastUpdated }: HealthPanelProps) {
  const statusClass = error ? "error" : health?.status === "ok" ? "ok" : "";

  return (
    <section className="panel">
      <h2>Backend Health</h2>
      <div className={`status-pill ${statusClass}`}>
        <span />
        {error ? "Offline" : health?.status ?? "Unknown"}
      </div>
      <p className="meta">
        Agents registered: {health?.agents_registered ?? "-"}
      </p>
      <p className="meta">Last check: {lastUpdated ?? "-"}</p>
      {error ? <p className="meta">{error}</p> : null}
    </section>
  );
}
