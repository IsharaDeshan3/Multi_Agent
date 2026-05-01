export type HealthResponse = {
  status: string;
  agents_registered: number;
};

export type ReviewState = {
  raw_text: string;
  research_data: Record<string, unknown>;
  audit_results: Record<string, unknown>;
  critique_notes: string;
  final_report?: FinalReport | null;
  final_feedback: string;
  logs: string[];
};

export type FinalReportScorecard = {
  novelty: number;
  rigor: number;
  clarity: number;
  narrative: string;
};

export type FinalReport = {
  executive_summary: string;
  recommendation: string;
  final_verdict: string;
  scorecard: FinalReportScorecard;
  evidence_log: string[];
  limitations: string[];
  ethical_considerations: string[];
  failure_cases: string[];
  source_provenance: Record<string, unknown>;
  next_steps: string[];
  markdown: string;
};

export type RunStatus = {
  run_id: string;
  status: string;
  current_stage: string;
  stage_index: number;
  stage_total: number;
  started_at: string;
  updated_at: string;
  messages: string[];
  error?: string | null;
  result_state?: ReviewState | null;
  source_url?: string | null;
  resolved_source_url?: string | null;
  source_content_type?: string | null;
  source_artifact_path?: string | null;
  source_status?: string | null;
};

export type PipelineRunRequest = {
  parser_input_path?: string;
  paper_url?: string;
  state?: Partial<ReviewState>;
};

export type SourceSummary = {
  source_url?: string | null;
  resolved_source_url?: string | null;
  source_content_type?: string | null;
  source_artifact_path?: string | null;
  source_status?: string | null;
};
