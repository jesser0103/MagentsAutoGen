'use client';

import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, ArrowLeft, Clock3, Github, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react';
import { AppNav } from '@/components/AppNav';
import { ApprovalPanel } from '@/components/ApprovalPanel';
import { Header } from '@/components/Header';
import { KPIMetrics } from '@/components/KPIMetrics';
import { PlanEditor } from '@/components/PlanEditor';
import { SelfHealingPanel } from '@/components/SelfHealingPanel';
import { StageProgress } from '@/components/StageProgress';
import { StatusBadge } from '@/components/StatusBadge';
import { TabbedDashboard } from '@/components/TabbedDashboard';
import { TerminalConsole } from '@/components/TerminalConsole';
import { Button } from '@/components/ui/button';
import { useEventStream } from '@/hooks/useEventStream';
import { useFinops } from '@/hooks/useFinops';
import { useSession } from '@/lib/auth-client';
import { mergeWorkflowEvents, withBoundedEvents } from '@/lib/events';
import { approveRun, deleteRun, exportRunToGitHub, getRun, rejectRun } from '@/lib/api';
import { saveRunToHistory, removeRunFromHistory } from '@/lib/runHistory';
import { cn } from '@/lib/utils';
import type { WorkflowRun } from '@/lib/types';

const PROVIDER_MODE = process.env.NEXT_PUBLIC_PROVIDER_MODE || 'demo';
const MIN_REFRESH_INTERVAL_MS = 1_000;

const AgentGraph = dynamic(
  () => import('@/components/AgentGraph').then((module) => module.AgentGraph),
  {
    ssr: false,
    loading: () => <div className="h-[230px] animate-pulse rounded-2xl border border-white/[0.07] bg-white/[0.02]" />,
  },
);

interface RunDashboardProps {
  runId: string;
}

export function RunDashboard({ runId }: RunDashboardProps) {
  const router = useRouter();
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [runLoading, setRunLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isReplanning, setIsReplanning] = useState(false);
  const [rejectedFeedback, setRejectedFeedback] = useState<string | null>(null);
  const [githubExportUrl, setGithubExportUrl] = useState<string | null>(null);
  const { data: session } = useSession();
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshInFlightRef = useRef(false);
  const lastRefreshAtRef = useRef(0);
  const { events, connected, connectionState, error: streamError, retryAttempt } = useEventStream(runId);
  const { finops, loading: finopsLoading, error: finopsError } = useFinops(
    run?.run_id,
    run?.status,
    run?.token_usage.length
  );

  const refreshRun = useCallback(async (quiet = false) => {
    if (refreshInFlightRef.current) return null;

    refreshInFlightRef.current = true;
    lastRefreshAtRef.current = Date.now();
    if (!quiet) setRunLoading(true);

    try {
      const updated = withBoundedEvents(await getRun(runId));
      setRun(updated);
      setError(null);
      saveRunToHistory(updated);
      return updated;
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Could not load this workflow run.');
      return null;
    } finally {
      refreshInFlightRef.current = false;
      if (!quiet) setRunLoading(false);
    }
  }, [runId]);

  const scheduleRefresh = useCallback((immediate = false) => {
    if (refreshTimerRef.current !== null) return;

    const elapsed = Date.now() - lastRefreshAtRef.current;
    const delay = immediate ? 0 : Math.max(0, MIN_REFRESH_INTERVAL_MS - elapsed);
    refreshTimerRef.current = setTimeout(() => {
      refreshTimerRef.current = null;
      void refreshRun(true);
    }, delay);
  }, [refreshRun]);

  useEffect(() => {
    setRun(null);
    setError(null);
    setRunLoading(true);
    void refreshRun();

    return () => {
      if (refreshTimerRef.current !== null) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [refreshRun]);

  const latestEvent = events[events.length - 1];
  useEffect(() => {
    if (!latestEvent) return;

    setRun((current) => {
      if (!current || current.run_id !== runId) return current;
      return { ...current, events: mergeWorkflowEvents(current.events, [latestEvent]) };
    });
    // Event payloads update the live panels immediately; a bounded refresh reconciles
    // artifacts, scans, reviews, and status without one GET for every event.
    scheduleRefresh();
  }, [latestEvent, runId, scheduleRefresh]);

  useEffect(() => {
    if (connectionState === 'closed') scheduleRefresh(true);
  }, [connectionState, scheduleRefresh]);

  const handleApprove = async () => {
    if (!run) return;
    setLoading(true);
    setError(null);
    try {
      const approved = withBoundedEvents(await approveRun(run.run_id));
      setRun(approved);
      saveRunToHistory(approved);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Could not approve this run.');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async (feedback: string) => {
    if (!run) return;
    setLoading(true);
    setError(null);
    try {
      const updated = withBoundedEvents(await rejectRun(run.run_id, feedback));
      setRun(updated);
      saveRunToHistory(updated);
      // Mark as replanning so the UI shows feedback until the new plan arrives
      setIsReplanning(true);
      setRejectedFeedback(feedback);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Could not reject this run.');
    } finally {
      setLoading(false);
    }
  };

  // Clear replanning state once the backend has delivered a new plan
  useEffect(() => {
    if (isReplanning && run?.status === 'awaiting_approval') {
      setIsReplanning(false);
    }
  }, [isReplanning, run?.status]);

  const eventChannelStatus = connectionState === 'reconnecting'
    ? `Reconnecting… attempt ${retryAttempt}`
    : connectionState === 'connecting'
      ? 'Connecting event channel…'
      : connectionState === 'closed'
        ? 'Event stream completed'
        : connected
          ? 'Event channel live'
          : 'Event channel unavailable';
  const userRole = session?.user?.role || 'operator';
  const isApprover = userRole === 'approver' || userRole === 'administrator';
  const isSubmitter = Boolean(
    session?.user?.id && run?.submitted_by_user_id === session.user.id
  );
  // Local demo mode has no authenticated session; the API's local-dev identity
  // remains usable there. Production authorization is always enforced by FastAPI.
  const canDecide = !session || (isApprover && !isSubmitter);

  return (
    <div className="relative min-h-screen overflow-x-hidden text-foreground">
      <div className="pointer-events-none fixed left-[-10rem] top-32 h-80 w-80 rounded-full bg-cyan-500/[0.05] blur-[100px]" />
      <div className="pointer-events-none fixed right-[-8rem] top-52 h-96 w-96 rounded-full bg-violet-500/[0.06] blur-[120px]" />
      <Header providerMode={PROVIDER_MODE} connectionState={connectionState} />
      <AppNav />

      <main className="relative mx-auto max-w-[1600px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {error && (
          <div className="rounded-xl border border-red-400/20 bg-red-950/25 px-4 py-3 text-sm text-red-200 backdrop-blur-xl">
            {error}
          </div>
        )}
        {streamError && connectionState === 'reconnecting' && (
          <div className="rounded-xl border border-amber-300/20 bg-amber-950/20 px-4 py-3 text-sm text-amber-100 backdrop-blur-xl">
            {streamError}
          </div>
        )}

        {!run ? (
          <div className="glass-card mx-auto max-w-xl p-8 text-center">
            <p className="eyebrow">Workflow run</p>
            <h1 className="mt-3 text-xl font-semibold text-white">{runLoading ? 'Loading mission…' : 'Mission unavailable'}</h1>
            {!runLoading && <p className="mt-3 text-sm text-slate-400">The run may not exist or the API is unavailable.</p>}
            <Button className="mt-5" variant="outline" onClick={() => router.push('/')}>Return to dashboard</Button>
          </div>
        ) : (
          <div className="animate-fade-in space-y-5 pb-20">
            <section className="glass-panel panel-highlight overflow-hidden px-5 py-5 sm:px-6">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
                <div className="min-w-0">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="status-dot" />
                    <span className="eyebrow">Active mission</span>
                    <span className="font-mono text-[9px] text-slate-600">/{run.run_id.slice(0, 8)}</span>
                  </div>
                  <h1 className="max-w-4xl text-balance text-xl font-semibold tracking-tight text-white sm:text-2xl">
                    {run.user_request}
                  </h1>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <div className="hidden items-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.025] px-3 py-2 text-[10px] text-slate-500 sm:flex">
                    <Clock3 className="h-3.5 w-3.5" /> Runtime tracked
                  </div>
                  <Button size="sm" variant="outline" onClick={() => void refreshRun()} className="h-9 border-white/10 bg-white/[0.025]">
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5" /> Sync
                  </Button>
                  {run.status === 'completed' && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={loading}
                      className="h-9 border-violet-300/20 bg-violet-300/[0.05] text-violet-100"
                      onClick={async () => {
                        setLoading(true);
                        setError(null);
                        try {
                          const result = await exportRunToGitHub(run.run_id);
                          setGithubExportUrl(result.pull_request_url);
                        } catch (caught: unknown) {
                          setError(caught instanceof Error ? caught.message : 'Could not export to GitHub.');
                        } finally {
                          setLoading(false);
                        }
                      }}
                    >
                      <Github className="mr-1.5 h-3.5 w-3.5" /> Export PR
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-9 border-red-400/20 bg-red-500/[0.06] text-red-300 hover:bg-red-500/20 hover:text-red-200"
                    onClick={async () => {
                      if (!confirm('Delete this mission permanently? This cannot be undone.')) return;
                      try {
                        await deleteRun(runId);
                        removeRunFromHistory(runId);
                        router.push('/runs');
                      } catch (err) {
                        alert('Failed to delete: ' + err);
                      }
                    }}
                  >
                    <Trash2 className="mr-1.5 h-3.5 w-3.5" /> Delete
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => router.push('/')} className="h-9 border-cyan-300/20 bg-cyan-300/[0.05] text-cyan-100">
                    <ArrowLeft className="mr-1.5 h-3.5 w-3.5" /> New mission
                  </Button>
                </div>
              </div>
            </section>

            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-4">
                <div className="glass-card panel-highlight p-4">
                  <div className="mb-4 flex items-center justify-between">
                    <p className="data-label">Workflow state</p>
                    <Activity className="h-3.5 w-3.5 text-cyan-300" />
                  </div>
                  <StatusBadge status={run.status} />
                  <p className="mt-3 break-all font-mono text-[9px] leading-4 text-slate-600">{run.run_id}</p>
                  <p className={`mt-3 flex items-center gap-2 border-t border-white/[0.06] pt-3 text-[9px] uppercase tracking-wider ${connected ? 'text-emerald-400' : connectionState === 'reconnecting' ? 'text-amber-300' : 'text-slate-500'}`}>
                    <span
                      className={cn(
                        'inline-flex h-2 w-2 rounded-full transition-colors',
                        connected
                          ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]'
                          : connectionState === 'reconnecting' || connectionState === 'connecting'
                          ? 'bg-amber-400 animate-pulse shadow-[0_0_8px_rgba(251,191,36,0.6)]'
                          : 'bg-slate-600'
                      )}
                    /> {eventChannelStatus}
                  </p>
                </div>

                <div className="glass-card p-4">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" /> Safety posture
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <div className="rounded-lg bg-white/[0.025] p-2.5"><p className="font-mono text-sm text-white">{run.scans.length}</p><p className="mt-1 text-[9px] text-slate-600">SCANS</p></div>
                    <div className="rounded-lg bg-white/[0.025] p-2.5"><p className="font-mono text-sm text-white">{run.reviews.length}</p><p className="mt-1 text-[9px] text-slate-600">REVIEWS</p></div>
                  </div>
                </div>
              </aside>

              <div className="min-w-0 space-y-5">
                <div className="glass-card px-5 py-4"><StageProgress status={run.status} /></div>
                <div>
                  <div className="mb-3 flex items-end justify-between">
                    <div><p className="eyebrow">Orchestration map</p><h2 className="mt-1 text-base font-semibold text-white">Agent execution fabric</h2></div>
                    <p className="hidden font-mono text-[9px] uppercase tracking-wider text-slate-600 sm:block">Select a node to inspect</p>
                  </div>
                  <AgentGraph status={run.status} events={run.events} />
                </div>
                <KPIMetrics run={run} finops={finops} />

                {/* Self-healing loop — shown while Coder is auto-revising after reviewer rejection */}
                <SelfHealingPanel
                  run={run}
                  maxRounds={Number(process.env.NEXT_PUBLIC_MAX_REVIEW_ROUNDS) || 3}
                />

                {/* Re-planning banner — shown after operator rejects a plan */}
                {isReplanning && (
                  <div className="flex items-start gap-3 rounded-xl border border-violet-400/25 bg-violet-950/20 px-4 py-3 text-sm text-violet-100 backdrop-blur-xl animate-fade-in">
                    <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-violet-400 animate-pulse shadow-[0_0_8px_rgba(167,139,250,0.8)]" />
                    <div>
                      <p className="font-semibold text-violet-200">Re-planning in progress…</p>
                      {rejectedFeedback && (
                        <p className="mt-1 text-[11px] text-violet-300/70 leading-5">
                          Feedback sent: <span className="italic">&ldquo;{rejectedFeedback}&rdquo;</span>
                        </p>
                      )}
                      <p className="mt-1 text-[11px] text-violet-400/60">The Planner is incorporating your feedback. A new plan will appear shortly.</p>
                    </div>
                  </div>
                )}

                {run.status === 'blocked' && (
                  <div className="rounded-xl border border-red-400/30 bg-red-950/20 p-4 text-sm text-red-200">
                    <strong>Blocked by Input Shield:</strong> {run.events[run.events.length - 1]?.message}
                  </div>
                )}

                {githubExportUrl && (
                  <div className="rounded-xl border border-emerald-400/30 bg-emerald-950/20 p-4 text-sm text-emerald-100">
                    Pull request created: <a className="underline" href={githubExportUrl} target="_blank" rel="noreferrer">Open on GitHub</a>
                  </div>
                )}

                {run.plan && (
                  <>
                    <PlanEditor
                      plan={run.plan}
                      runId={run.run_id}
                      editable={run.status === 'awaiting_approval'}
                      onPlanSaved={(plan) => {
                        const updated = { ...run, plan };
                        setRun(updated);
                        saveRunToHistory(updated);
                      }}
                    />
                    {/*
                  <div className="glass-card panel-highlight p-5">
                    <div className="flex items-center justify-between"><div><p className="eyebrow">Approved intent</p><h2 className="mt-1 text-sm font-semibold text-white">Execution plan</h2></div><span className="font-mono text-[9px] text-slate-600">{run.plan.steps.length} STEPS</span></div>
                    <p className="mt-4 text-sm leading-6 text-slate-300">{run.plan.summary}</p>
                    <ol className="mt-4 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
                      {run.plan.steps.map((step, index) => (
                        <li key={index} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                          <span className="mr-2 font-mono text-cyan-300">0{index + 1}</span>
                          <strong className="capitalize text-slate-200">{step.language}</strong> — {step.description}
                        </li>
                      ))}
                    </ol>
                  </div>
                    */}
                  </>
                )}

                <TabbedDashboard
                  run={run}
                  events={events}
                  finops={finops}
                  finopsLoading={finopsLoading}
                  finopsError={finopsError}
                />
                <ApprovalPanel
                  run={run}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  loading={loading}
                  isReplanning={isReplanning}
                  canDecide={canDecide}
                />
              </div>
            </div>
          </div>
        )}

        <div className="h-14" />
      </main>

      <TerminalConsole
        events={events}
        runEvents={run?.events || []}
        connected={connected}
        connectionState={connectionState}
      />
    </div>
  );
}
