export interface WorkflowRun {
  run_id: string;
  user_request: string;
  submitted_by_user_id: string | null;
  status: string;
  event_schema_version: number;
  plan: Plan | null;
  retrieved_rules: string[];
  retrieval_evidence: RetrievalEvidence[];
  context_audits: ContextAudit[];
  artifacts: Artifact[];
  scans: ScanReport[];
  reviews: ReviewResult[];
  sandbox_results: SandboxResult[];
  finops_reports?: FinOpsReport[];
  red_team_reports?: RedTeamReport[];
  auto_fix_attempts: number;
  token_usage: TokenUsageRecord[];
  events: WorkflowEvent[];
}

export interface AttackFinding {
  rule_id: string;
  severity: string;
  vector: string;
  message: string;
  remediation: string;
  exploit_scenario: string;
}

export interface RedTeamReport {
  assessment: string;
  risk_score: number;
  attack_findings: AttackFinding[];
}

export interface FinOpsCostDriver {
  resource_type: string;
  estimated_monthly_usd: number;
  sku: string;
  notes: string;
}

export interface InfracostResource {
  name: string;
  resource_type: string;
  monthly_cost_usd: number;
}

export interface InfracostBreakdown {
  total_monthly_usd: number;
  currency: string;
  resources: InfracostResource[];
  error: string | null;
}

export interface FinOpsReport {
  total_monthly_usd: number;
  currency: string;
  cost_drivers: FinOpsCostDriver[];
  recommendations: string[];
  raw_assessment: string;
  infracost_breakdown: InfracostBreakdown | null;
}

export interface TokenUsageRecord {
  record_id: string;
  agent: string;
  stage: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  operation: string;
  max_tokens: number | null;
  created_at: string;
}

export interface Plan {
  summary: string;
  steps: PlanStep[];
  open_questions: string[];
  ready_for_approval: boolean;
}

export interface PlanStep {
  language: string;
  description: string;
}

export interface RetrievalEvidence {
  rule_id: string;
  source: string;
  source_hash: string;
  score: number;
}

export interface ContextAudit {
  original_characters: number;
  sent_characters: number;
  omitted_characters: number;
  omitted_sha256: string | null;
}

export interface Artifact {
  language: string;
  filename: string;
  content: string;
}

export interface ScanReport {
  tool: string;
  succeeded: boolean;
  findings: SecurityFinding[];
  error: string | null;
}

export interface SecurityFinding {
  rule_id: string;
  severity: string;
  message: string;
  remediation: string;
  tool: string;
  location: string | null;
  evidence: string | null;
}

export interface ReviewResult {
  verdict: string;
  assessment: string;
  findings: SecurityFinding[];
  required_changes: string[];
}

export interface SandboxResult {
  succeeded: boolean;
  summary: string;
  output: string;
}

export interface WorkflowEvent {
  event_type: string;
  agent: string;
  message: string;
  created_at: string;
}

export interface FinOpsSummary {
  run_id: string;
  status: string;
  total_usd: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  per_agent: Record<string, number>;
  per_stage: Record<string, number>;
  per_operation: Record<string, number>;
  disclaimer: string;
}

export interface GitHubExportResult {
  branch: string;
  pull_request_number: number;
  pull_request_url: string;
}
