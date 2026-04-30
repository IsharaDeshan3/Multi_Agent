import type { RunStatus } from "../lib/types";

const STAGES = [
  { key: "parser", label: "Parser" },
  { key: "auditor", label: "Auditor" },
  { key: "critic", label: "Critic" },
  { key: "integrator", label: "Integrator" },
];

type WorkflowPanelProps = {
  runStatus: RunStatus | null;
};

function getStageState(stageKey: string, runStatus: RunStatus | null) {
  if (!runStatus) {
    return "pending";
  }

  const { status, current_stage } = runStatus;
  const currentIndex = STAGES.findIndex((stage) => stage.key === current_stage);
  const stageIndex = STAGES.findIndex((stage) => stage.key === stageKey);

  if (status === "failed" && stageIndex === currentIndex) {
    return "failed";
  }

  if (status === "completed") {
    return stageIndex <= currentIndex ? "done" : "pending";
  }

  if (status === "running" || status === "queued") {
    if (currentIndex === -1) {
      return "pending";
    }
    if (stageIndex < currentIndex) {
      return "done";
    }
    if (stageIndex === currentIndex) {
      return "active";
    }
  }

  return "pending";
}

export function WorkflowPanel({ runStatus }: WorkflowPanelProps) {
  return (
    <section className="panel">
      <h2>Workflow Progress</h2>
      <div className="workflow">
        {STAGES.map((stage, index) => {
          const state = getStageState(stage.key, runStatus);
          return (
            <div key={stage.key} className={`stage ${state}`}>
              <div>
                <div className="badge">Step {index + 1}</div>
                <div className="name">{stage.label}</div>
              </div>
              <div className="meta">
                {state === "active" && "Running"}
                {state === "done" && "Completed"}
                {state === "failed" && "Failed"}
                {state === "pending" && "Pending"}
              </div>
            </div>
          );
        })}
      </div>
      <p className="meta">
        Current stage: {runStatus?.current_stage ?? "Not started"}
      </p>
    </section>
  );
}
