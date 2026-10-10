'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { AppNav } from '@/components/AppNav';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { listRuns, deleteRun } from '@/lib/api';
import { loadRunHistory, removeRunFromHistory } from '@/lib/runHistory';
import type { WorkflowRun } from '@/lib/types';
import type { RunHistoryEntry } from '@/lib/runHistory';
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  Filter,
  Layers,
  MoveUpRight,
  RotateCcw,
  Search,
  ShieldCheck,
  Trash2,
} from 'lucide-react';

const PROVIDER_MODE = process.env.NEXT_PUBLIC_PROVIDER_MODE || 'demo';

type StatusFilter = 'all' | 'awaiting_approval' | 'completed' | 'blocked' | 'in_progress';

export default function MissionsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [localHistory, setLocalHistory] = useState<RunHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const data = await listRuns(50);
      setRuns(data);
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this mission? This cannot be undone.')) return;
    setDeletingId(runId);
    try {
      await deleteRun(runId);
      removeRunFromHistory(runId);
      setRuns((prev) => prev.filter((r) => r.run_id !== runId));
      setLocalHistory((prev) => prev.filter((h) => h.run_id !== runId));
    } catch (err) {
      alert('Failed to delete mission: ' + err);
    } finally {
      setDeletingId(null);
    }
  };

  useEffect(() => {
    setLocalHistory(loadRunHistory());
    void fetchRuns();
  }, []);

  const openRun = (runId: string) => {
    router.push(`/runs/${encodeURIComponent(runId)}`);
  };

  // Merge API runs with any local history entries not yet in API
  const allRunIds = new Set(runs.map((r) => r.run_id));
  const mergedRuns: Array<{
    run_id: string;
    user_request: string;
    status: string;
    scansCount?: number;
    reviewsCount?: number;
  }> = [
    ...runs.map((r) => ({
      run_id: r.run_id,
      user_request: r.user_request,
      status: r.status,
      scansCount: r.scans?.length ?? 0,
      reviewsCount: r.reviews?.length ?? 0,
    })),
    ...localHistory
      .filter((h) => !allRunIds.has(h.run_id))
      .map((h) => ({
        run_id: h.run_id,
        user_request: h.user_request,
        status: h.status,
      })),
  ];

  const filteredRuns = mergedRuns.filter((r) => {
    const matchesSearch =
      r.user_request.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.run_id.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;

    if (statusFilter === 'all') return true;
    if (statusFilter === 'awaiting_approval')
      return r.status === 'awaiting_approval' || r.status === 'needs_clarification';
    if (statusFilter === 'completed') return r.status === 'completed';
    if (statusFilter === 'blocked') return r.status === 'blocked';
    if (statusFilter === 'in_progress')
      return (
        r.status !== 'completed' &&
        r.status !== 'blocked' &&
        r.status !== 'awaiting_approval' &&
        r.status !== 'needs_clarification'
      );
    return true;
  });

  const pendingApprovalsCount = mergedRuns.filter(
    (r) => r.status === 'awaiting_approval' || r.status === 'needs_clarification'
  ).length;

  return (
    <div className="relative min-h-screen overflow-x-hidden text-foreground pb-20">
      <div className="pointer-events-none fixed left-[-10rem] top-32 h-80 w-80 rounded-full bg-cyan-500/[0.05] blur-[100px]" />
      <div className="pointer-events-none fixed right-[-8rem] top-52 h-96 w-96 rounded-full bg-violet-500/[0.06] blur-[120px]" />

      <Header providerMode={PROVIDER_MODE} />
      <AppNav pendingApprovalsCount={pendingApprovalsCount} />

      <main className="relative mx-auto max-w-[1600px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {/* Header section */}
        <section className="glass-panel panel-highlight p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <Layers className="h-4 w-4 text-cyan-300" />
                <span className="eyebrow">Operations Hub</span>
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-white">
                Missions & Workflows
              </h1>
              <p className="mt-1 text-xs text-slate-400">
                Audit, track, and inspect all autonomous infrastructure operations.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => void fetchRuns()}
                disabled={loading}
                className="h-9 border-white/10 bg-white/[0.03]"
              >
                <RotateCcw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Sync
              </Button>
              <Link href="/">
                <Button size="sm" className="h-9 bg-cyan-300 text-slate-950 font-semibold hover:bg-cyan-200">
                  New Mission <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          </div>
        </section>

        {/* Filter and search bar */}
        <section className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            {(
              [
                ['all', 'All Missions', mergedRuns.length],
                ['awaiting_approval', 'Awaiting Approval', pendingApprovalsCount],
                ['in_progress', 'In Progress', mergedRuns.filter((r) => r.status !== 'completed' && r.status !== 'blocked' && r.status !== 'awaiting_approval' && r.status !== 'needs_clarification').length],
                ['completed', 'Completed', mergedRuns.filter((r) => r.status === 'completed').length],
                ['blocked', 'Blocked', mergedRuns.filter((r) => r.status === 'blocked').length],
              ] as const
            ).map(([key, label, count]) => (
              <button
                key={key}
                onClick={() => setStatusFilter(key)}
                className={`flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium transition ${
                  statusFilter === key
                    ? 'border border-cyan-300/30 bg-cyan-300/[0.08] text-white shadow-[0_0_15px_rgba(34,211,238,0.1)]'
                    : 'border border-transparent text-slate-400 hover:border-white/[0.06] hover:bg-white/[0.02] hover:text-slate-200'
                }`}
              >
                <span>{label}</span>
                <span className="rounded-full bg-white/[0.06] px-1.5 py-0.2 font-mono text-[9px] text-slate-400">
                  {count}
                </span>
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search prompt or ID…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl border border-white/[0.08] bg-black/20 pl-9 pr-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:border-cyan-300/40 focus:outline-none"
            />
          </div>
        </section>

        {/* Missions Table / Cards */}
        {filteredRuns.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <p className="eyebrow">No Missions Found</p>
            <h3 className="mt-2 text-base font-semibold text-white">No workflows match your filter criteria.</h3>
            <p className="mt-1 text-xs text-slate-500">
              Try adjusting your search query or initialize a new mission from the overview.
            </p>
            <Link href="/">
              <Button size="sm" variant="outline" className="mt-4 border-cyan-300/20 bg-cyan-300/[0.05] text-cyan-200">
                Launch New Mission
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-2.5">
            {filteredRuns.map((run) => (
              <div
                key={run.run_id}
                onClick={() => openRun(run.run_id)}
                className="glass-card panel-highlight group flex flex-col gap-4 p-4 transition duration-200 hover:-translate-y-0.5 hover:border-cyan-300/30 cursor-pointer sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 space-y-1.5 flex-1 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
                      /{run.run_id.slice(0, 8)}
                    </span>
                    <StatusBadge status={run.status} />
                  </div>
                  <h3 className="text-sm font-medium text-slate-200 group-hover:text-cyan-100 transition line-clamp-2">
                    {run.user_request}
                  </h3>
                </div>

                <div className="flex shrink-0 items-center gap-4 text-xs text-slate-400 border-t border-white/[0.06] pt-3 sm:border-t-0 sm:pt-0">
                  {run.scansCount !== undefined && (
                    <div className="flex items-center gap-1 font-mono text-[11px]">
                      <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                      <span>{run.scansCount} scans</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1 text-[11px] text-cyan-300 font-medium group-hover:translate-x-1 transition">
                    <span>Inspect</span>
                    <MoveUpRight className="h-3.5 w-3.5" />
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, run.run_id)}
                    disabled={deletingId === run.run_id}
                    title="Delete Mission"
                    className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
