import { FinOpsSummary, GitHubExportResult, Plan, WorkflowRun } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || process.env.MAGENT_API_KEY || '';

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  // Prefer a Better Auth JWT when a session exists, fall back to API key.
  let authHeader: Record<string, string> = {};
  try {
    const tokenResponse = await fetch('/api/auth/token', { credentials: 'include' });
    const jwt = tokenResponse.ok
      ? await tokenResponse.json() as { token?: string }
      : null;
    if (jwt?.token) {
      authHeader = { Authorization: `Bearer ${jwt.token}` };
    } else if (API_KEY) {
      authHeader = { 'X-API-Key': API_KEY };
    }
  } catch {
    // Auth client not available (e.g. SSR context) — fall back to API key
    if (API_KEY) authHeader = { 'X-API-Key': API_KEY };
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...authHeader,
    ...(options?.headers as Record<string, string> | undefined),
  };
  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

export async function submitRun(userRequest: string): Promise<WorkflowRun> {
  return api<WorkflowRun>('/api/runs', {
    method: 'POST',
    body: JSON.stringify({ user_request: userRequest }),
  });
}

export async function listRuns(limit: number = 50): Promise<WorkflowRun[]> {
  return api<WorkflowRun[]>(`/api/runs?limit=${limit}`);
}

export async function getRun(runId: string): Promise<WorkflowRun> {
  return api<WorkflowRun>(`/api/runs/${runId}`);
}

export async function approveRun(runId: string): Promise<WorkflowRun> {
  return api<WorkflowRun>(`/api/runs/${runId}/approve`, { method: 'POST' });
}

export async function rejectRun(runId: string, feedback: string): Promise<WorkflowRun> {
  return api<WorkflowRun>(`/api/runs/${runId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ feedback }),
  });
}

export async function updatePlan(runId: string, plan: Plan): Promise<Plan> {
  return api<Plan>(`/api/runs/${runId}/plan`, {
    method: 'PATCH',
    body: JSON.stringify({ summary: plan.summary, steps: plan.steps }),
  });
}

export async function exportRunToGitHub(runId: string): Promise<GitHubExportResult> {
  return api<GitHubExportResult>(`/api/runs/${runId}/export/github`, { method: 'POST' });
}

export async function deleteRun(runId: string): Promise<{ status: string; run_id: string }> {
  return api<{ status: string; run_id: string }>(`/api/runs/${runId}`, {
    method: 'DELETE',
  });
}

export async function getFinops(runId: string): Promise<FinOpsSummary> {
  return api<FinOpsSummary>(`/api/runs/${runId}/finops`, { cache: 'no-store' });
}

export function createEventStream(runId: string): EventSource {
  return new EventSource(`${API_BASE}/api/runs/${runId}/events/stream`);
}
