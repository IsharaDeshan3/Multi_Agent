"use client";

import { useCallback, useEffect, useState } from "react";

import { HealthPanel } from "../components/HealthPanel";
import { LogPanel } from "../components/LogPanel";
import { SourcePanel } from "../components/SourcePanel";
import { RunPanel } from "../components/RunPanel";
import { WorkflowPanel } from "../components/WorkflowPanel";
import { getHealth, getRunStatus, startRun } from "../lib/api";
import type { HealthResponse, PipelineRunRequest, RunStatus } from "../lib/types";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthCheckedAt, setHealthCheckedAt] = useState<string | null>(null);

  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  const refreshHealth = useCallback(async () => {
    try {
      const data = await getHealth();
      setHealth(data);
      setHealthError(null);
      setHealthCheckedAt(new Date().toLocaleTimeString());
    } catch (error) {
      setHealthError((error as Error).message);
      setHealthCheckedAt(new Date().toLocaleTimeString());
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    const interval = setInterval(refreshHealth, 15000);
    return () => clearInterval(interval);
  }, [refreshHealth]);

  useEffect(() => {
    if (!runStatus) {
      return;
    }

    if (runStatus.status !== "running" && runStatus.status !== "queued") {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updated = await getRunStatus(runStatus.run_id);
        setRunStatus(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          clearInterval(interval);
        }
      } catch (error) {
        setRunError((error as Error).message);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [runStatus?.run_id, runStatus?.status]);

  const handleStart = async (payload: {
    parserInputPath?: string;
    rawText?: string;
    paperUrl?: string;
  }) => {
    setIsStarting(true);
    setRunError(null);

    const requestPayload: PipelineRunRequest = {};
    if (payload.paperUrl) {
      requestPayload.paper_url = payload.paperUrl;
    }
    if (payload.parserInputPath) {
      requestPayload.parser_input_path = payload.parserInputPath;
    }
    if (payload.rawText) {
      requestPayload.state = { raw_text: payload.rawText };
    }

    try {
      const run = await startRun(requestPayload);
      setRunStatus(run);
    } catch (error) {
      setRunError((error as Error).message);
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="header">
        <p className="kicker">Agentic Review Control Room</p>
        <h1>Research Review Dashboard</h1>
        <p>
          Track backend health, launch the review pipeline, and watch each stage
          progress in real time.
        </p>
      </header>

      <section className="grid">
        <HealthPanel
          health={health}
          error={healthError}
          lastUpdated={healthCheckedAt}
        />
        <SourcePanel runStatus={runStatus} />
        <WorkflowPanel runStatus={runStatus} />
        <RunPanel onStart={handleStart} isStarting={isStarting} />
      </section>

      <section className="grid">
        <LogPanel runStatus={runStatus} error={runError} />
      </section>
    </main>
  );
}
