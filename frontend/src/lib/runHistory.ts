import type { WorkflowRun } from './types';

const STORAGE_KEY = 'magents_recent_runs';
const MAX_RUNS = 20;

/**
 * A slimmed-down representation of a workflow run for localStorage persistence.
 * We avoid storing the full WorkflowRun (events, artifacts, scans) to stay
 * within the ~5 MB localStorage quota.
 */
export interface RunHistoryEntry {
  run_id: string;
  user_request: string;
  status: string;
  created_at: string; // ISO 8601 timestamp
}

/** Read persisted run history from localStorage. Returns [] on any error. */
export function loadRunHistory(): RunHistoryEntry[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Basic shape validation — discard malformed entries silently
    return parsed.filter(
      (entry: unknown): entry is RunHistoryEntry =>
        typeof entry === 'object' &&
        entry !== null &&
        typeof (entry as RunHistoryEntry).run_id === 'string' &&
        typeof (entry as RunHistoryEntry).user_request === 'string',
    );
  } catch {
    return [];
  }
}

/** Upsert a run into the persisted history list (most-recent first, capped). */
export function saveRunToHistory(run: WorkflowRun): void {
  if (typeof window === 'undefined') return;
  try {
    const existing = loadRunHistory();
    const entry: RunHistoryEntry = {
      run_id: run.run_id,
      user_request: run.user_request,
      status: run.status,
      created_at: new Date().toISOString(),
    };
    // Upsert: remove any previous entry with same run_id, prepend new one
    const updated = [entry, ...existing.filter((e) => e.run_id !== run.run_id)].slice(0, MAX_RUNS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // localStorage full or unavailable — fail silently
  }
}

/** Remove a single run from persisted history. */
export function removeRunFromHistory(runId: string): void {
  if (typeof window === 'undefined') return;
  try {
    const existing = loadRunHistory();
    const updated = existing.filter((e) => e.run_id !== runId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // fail silently
  }
}

/** Clear all persisted run history (useful for settings / testing). */
export function clearRunHistory(): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // fail silently
  }
}
