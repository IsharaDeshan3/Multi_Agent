import type { HealthResponse, PipelineRunRequest, RunStatus } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/v1/health");
}

export function startRun(payload: PipelineRunRequest): Promise<RunStatus> {
  return requestJson<RunStatus>("/api/v1/pipelines/review/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getRunStatus(runId: string): Promise<RunStatus> {
  return requestJson<RunStatus>(`/api/v1/pipelines/review/runs/${runId}`);
}
