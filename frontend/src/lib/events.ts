import type { WorkflowEvent, WorkflowRun } from '@/lib/types';

export const MAX_RENDERED_EVENTS = 500;

export function eventKey(event: WorkflowEvent): string {
  return `${event.created_at}\u0000${event.message}`;
}

/** Merge event sequences without repeated linear scans and retain a bounded UI history. */
export function mergeWorkflowEvents(
  current: WorkflowEvent[],
  incoming: WorkflowEvent[],
  limit = MAX_RENDERED_EVENTS,
): WorkflowEvent[] {
  const seen = new Set(current.map(eventKey));
  const merged = [...current];

  for (const event of incoming) {
    const key = eventKey(event);
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(event);
    }
  }

  return merged.length > limit ? merged.slice(-limit) : merged;
}

/** Prevent a long-lived run response from making event-driven panels expensive to render. */
export function withBoundedEvents(run: WorkflowRun): WorkflowRun {
  return run.events.length > MAX_RENDERED_EVENTS
    ? { ...run, events: run.events.slice(-MAX_RENDERED_EVENTS) }
    : run;
}
