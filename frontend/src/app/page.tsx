'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AppNav } from '@/components/AppNav';
import { Header } from '@/components/Header';
import { StatusBadge } from '@/components/StatusBadge';
import { listRuns } from '@/lib/api';
import { loadRunHistory } from '@/lib/runHistory';
import type { RunHistoryEntry } from '@/lib/runHistory';
import type { WorkflowRun } from '@/lib/types';
import {
  ArrowRight,
  Bot,
  Fingerprint,
  Rocket,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react';

const PROVIDER_MODE = process.env.NEXT_PUBLIC_PROVIDER_MODE || 'demo';

interface OverviewRun {
  run_id: string;
  user_request: string;
  status: string;
}

export default function OverviewPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [recentRuns, setRecentRuns] = useState<RunHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setRecentRuns(loadRunHistory());
    listRuns(20)
      .then(setRuns)
      .catch(() => {
        // Local history remains available when the API cannot be reached.
      })
      .finally(() => setLoading(false));
  }, []);

  const pendingApprovals = runs.filter(
    (run) => run.status === 'awaiting_approval' || run.status === 'needs_clarification'
  );
  const completedCount = runs.filter((run) => run.status === 'completed').length;
  const overviewRuns: OverviewRun[] = runs.length > 0
    ? runs.map(({ run_id, user_request, status }) => ({ run_id, user_request, status }))
    : recentRuns.map(({ run_id, user_request, status }) => ({ run_id, user_request, status }));

  const openRun = (runId: string) => router.push(`/runs/${encodeURIComponent(runId)}`);

  return (
    <div className="relative min-h-screen overflow-x-hidden pb-20 text-foreground">
      <div className="pointer-events-none fixed left-[-10rem] top-32 h-80 w-80 rounded-full bg-cyan-500/[0.05] blur-[100px]" />
      <div className="pointer-events-none fixed right-[-8rem] top-52 h-96 w-96 rounded-full bg-violet-500/[0.06] blur-[120px]" />

      <Header providerMode={PROVIDER_MODE} />
      <AppNav pendingApprovalsCount={pendingApprovals.length} />

      <main className="relative mx-auto max-w-[1600px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="glass-panel panel-highlight flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="eyebrow">Overview</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              Control plane overview
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Monitor mission activity, human approvals, security outcomes, and the active agent mesh.
            </p>
          </div>
          <Link
            href="/new-mission"
            className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-cyan-300 px-5 text-xs font-semibold text-slate-950 shadow-[0_0_28px_rgba(34,211,238,0.2)] transition-all hover:-translate-y-0.5 hover:bg-cyan-200"
          >
            <Sparkles className="h-4 w-4" /> New mission
          </Link>
        </section>

        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Total Missions</p>
              <Zap className="h-4 w-4 text-cyan-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-white">{overviewRuns.length}</p>
            <p className="mt-1 text-[10px] text-slate-500">Autonomous workflow runs</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Pending Approval</p>
              <Fingerprint className="h-4 w-4 text-amber-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-amber-200">{pendingApprovals.length}</p>
            <p className="mt-1 text-[10px] text-slate-500">Human authorization gates</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Completed Clean</p>
              <ShieldCheck className="h-4 w-4 text-emerald-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-emerald-300">{completedCount}</p>
            <p className="mt-1 text-[10px] text-slate-500">Passed SAST & Sandbox</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Active Mesh Nodes</p>
              <Bot className="h-4 w-4 text-violet-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-violet-300">5 / 5</p>
            <p className="mt-1 text-[10px] text-slate-500">Planner, Coder, Reviewer, RAG, Sandbox</p>
          </div>
        </section>

        {pendingApprovals.length > 0 && (
          <section className="rounded-2xl border border-amber-300/30 bg-amber-950/20 p-5 shadow-[0_0_40px_rgba(251,191,36,0.06)] backdrop-blur-xl">
            <div className="mb-3 flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-amber-300" />
                <h2 className="text-sm font-semibold text-amber-100">
                  Human Approvals Required ({pendingApprovals.length})
                </h2>
              </div>
              <Link href="/runs" className="inline-flex items-center gap-1 text-xs text-amber-300 hover:text-amber-200">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {pendingApprovals.slice(0, 3).map((run) => (
                <button
                  key={run.run_id}
                  type="button"
                  onClick={() => openRun(run.run_id)}
                  className="glass-card group border-amber-300/20 p-4 text-left transition hover:border-amber-300/40 hover:bg-amber-300/[0.04]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[9px] uppercase tracking-wider text-slate-500">/{run.run_id.slice(0, 8)}</span>
                    <StatusBadge status={run.status} />
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs text-slate-200">{run.user_request}</p>
                  <div className="mt-3 flex items-center justify-between border-t border-white/[0.06] pt-2 text-[10px] text-amber-300">
                    <span>Review plan & authorize</span>
                    <ArrowRight className="h-3 w-3 transition group-hover:translate-x-1" />
                  </div>
                </button>
              ))}
            </div>
          </section>
        )}

        <section className="glass-card p-5 sm:p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Recent activity</p>
              <h2 className="mt-1 text-base font-semibold text-white">Latest missions</h2>
            </div>
            <Link href="/runs" className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200">
              All missions <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {loading ? (
            <p className="py-10 text-center text-xs text-slate-500">Loading mission activity…</p>
          ) : overviewRuns.length === 0 ? (
            <div className="mt-5 rounded-xl border border-dashed border-white/[0.08] px-5 py-10 text-center">
              <Rocket className="mx-auto h-6 w-6 text-slate-600" />
              <p className="mt-3 text-sm text-slate-300">No missions have been initialized yet.</p>
              <Link href="/new-mission" className="mt-2 inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200">
                Create the first mission <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          ) : (
            <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {overviewRuns.slice(0, 6).map((run) => (
                <button
                  key={run.run_id}
                  type="button"
                  onClick={() => openRun(run.run_id)}
                  className="group rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-left transition hover:border-cyan-300/20 hover:bg-cyan-300/[0.03]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[9px] text-slate-600">/{run.run_id.slice(0, 8)}</span>
                    <StatusBadge status={run.status} />
                  </div>
                  <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-300">{run.user_request}</p>
                  <div className="mt-3 flex justify-end"><ArrowRight className="h-3.5 w-3.5 text-slate-600 transition group-hover:translate-x-1 group-hover:text-cyan-300" /></div>
                </button>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
