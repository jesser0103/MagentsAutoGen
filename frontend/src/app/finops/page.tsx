'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { AppNav } from '@/components/AppNav';
import { Button } from '@/components/ui/button';
import { StatusBadge } from '@/components/StatusBadge';
import { listRuns, getFinops } from '@/lib/api';
import type { WorkflowRun, FinOpsSummary } from '@/lib/types';
import {
  CircleDollarSign,
  Gauge,
  Layers,
  MoveUpRight,
  PieChart,
  RotateCcw,
  Sparkles,
  TrendingUp,
  Zap,
} from 'lucide-react';

const PROVIDER_MODE = process.env.NEXT_PUBLIC_PROVIDER_MODE || 'demo';

export default function FinOpsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [summaries, setSummaries] = useState<Record<string, FinOpsSummary>>({});

  const loadData = async () => {
    setLoading(true);
    try {
      const runList = await listRuns(30);
      setRuns(runList);

      // Fetch FinOps for recent runs in parallel
      const results: Record<string, FinOpsSummary> = {};
      await Promise.all(
        runList.slice(0, 15).map(async (r) => {
          try {
            const summary = await getFinops(r.run_id);
            results[r.run_id] = summary;
          } catch {
            // Ignore missing
          }
        })
      );
      setSummaries(results);
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  // Compute aggregate totals
  const allSummaries = Object.values(summaries);
  const totalUsd = allSummaries.reduce((sum, s) => sum + (s.total_usd || 0), 0);
  const totalPromptTokens = allSummaries.reduce((sum, s) => sum + (s.total_prompt_tokens || 0), 0);
  const totalCompletionTokens = allSummaries.reduce((sum, s) => sum + (s.total_completion_tokens || 0), 0);
  const totalTokens = totalPromptTokens + totalCompletionTokens;
  const avgCost = allSummaries.length > 0 ? totalUsd / allSummaries.length : 0;

  // Aggregate agent spend
  const agentSpend: Record<string, number> = {};
  allSummaries.forEach((s) => {
    if (s.per_agent) {
      Object.entries(s.per_agent).forEach(([agent, cost]) => {
        agentSpend[agent] = (agentSpend[agent] || 0) + cost;
      });
    }
  });

  const pendingApprovalsCount = runs.filter(
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
                <CircleDollarSign className="h-4 w-4 text-cyan-300" />
                <span className="eyebrow">Cost & Telemetry Control</span>
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-white">
                FinOps Intelligence
              </h1>
              <p className="mt-1 text-xs text-slate-400">
                Track cumulative model consumption, token efficiency, and per-agent cloud spend.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void loadData()}
              disabled={loading}
              className="h-9 border-white/10 bg-white/[0.03]"
            >
              <RotateCcw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Telemetry
            </Button>
          </div>
        </section>

        {/* Top KPI Cards */}
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Total Spend</p>
              <CircleDollarSign className="h-4 w-4 text-cyan-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-white">
              ${totalUsd.toFixed(4)}
            </p>
            <p className="mt-1 text-[10px] text-slate-500">Across {allSummaries.length} tracked runs</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Total Token Volume</p>
              <Gauge className="h-4 w-4 text-violet-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-violet-200">
              {totalTokens.toLocaleString()}
            </p>
            <p className="mt-1 text-[10px] text-slate-500">
              {totalPromptTokens.toLocaleString()} in · {totalCompletionTokens.toLocaleString()} out
            </p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Avg Cost / Run</p>
              <TrendingUp className="h-4 w-4 text-emerald-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-emerald-300">
              ${avgCost.toFixed(4)}
            </p>
            <p className="mt-1 text-[10px] text-slate-500">Automated workflow average</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Model Engine</p>
              <Zap className="h-4 w-4 text-sky-300" />
            </div>
            <p className="mt-3 font-mono text-lg font-semibold text-sky-200">GPT-4o</p>
            <p className="mt-1 text-[10px] text-slate-500">Azure OpenAI Tier 1</p>
          </div>
        </section>

        {/* Spend by Agent Breakdown */}
        <section className="grid gap-6 lg:grid-cols-2">
          <div className="glass-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
              <div className="flex items-center gap-2">
                <PieChart className="h-4 w-4 text-cyan-300" />
                <h3 className="text-sm font-semibold text-white">Spend by Agent Role</h3>
              </div>
              <span className="font-mono text-[9px] text-slate-500">AGGREGATE</span>
            </div>

            <div className="space-y-3">
              {Object.keys(agentSpend).length === 0 ? (
                <p className="text-xs text-slate-500 py-6 text-center">Awaiting agent usage telemetry…</p>
              ) : (
                Object.entries(agentSpend).map(([agent, cost]) => {
                  const percentage = totalUsd > 0 ? (cost / totalUsd) * 100 : 0;
                  return (
                    <div key={agent} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-medium text-slate-200 capitalize">{agent} Agent</span>
                        <span className="font-mono text-slate-400">
                          ${cost.toFixed(4)} ({percentage.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-white/[0.04] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-violet-400 transition-all duration-500"
                          style={{ width: `${Math.max(4, Math.min(100, percentage))}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="glass-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-emerald-300" />
                <h3 className="text-sm font-semibold text-white">Token Efficiency Posture</h3>
              </div>
              <span className="font-mono text-[9px] text-slate-500">GOVERNANCE</span>
            </div>
            <p className="text-xs leading-5 text-slate-400">
              The bounded context manager enforces a token quota limit per stage, trimming redundant
              chat history and preventing runaway completions during coder-reviewer loops.
            </p>
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <p className="data-label">Prompt Cache Ratio</p>
                <p className="mt-1 font-mono text-base font-semibold text-slate-200">
                  {totalPromptTokens > 0 ? ((totalPromptTokens / (totalTokens || 1)) * 100).toFixed(0) : 0}%
                </p>
              </div>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <p className="data-label">Loop Review Cap</p>
                <p className="mt-1 font-mono text-base font-semibold text-emerald-300">5 max</p>
              </div>
            </div>
          </div>
        </section>

        {/* Per-Mission Cost Breakdown Table */}
        <section className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-violet-300" />
              <h3 className="text-sm font-semibold text-white">Mission Telemetry Ledger</h3>
            </div>
            <span className="font-mono text-[9px] text-slate-500">RECENT MISSIONS</span>
          </div>

          <div className="space-y-2">
            {runs.slice(0, 10).map((r) => {
              const summary = summaries[r.run_id];
              return (
                <div
                  key={r.run_id}
                  onClick={() => router.push(`/runs/${encodeURIComponent(r.run_id)}`)}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-xl border border-white/[0.05] bg-white/[0.015] p-3.5 hover:border-cyan-300/30 hover:bg-white/[0.03] transition cursor-pointer group"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[9px] uppercase tracking-wider text-slate-500">
                        /{r.run_id.slice(0, 8)}
                      </span>
                      <StatusBadge status={r.status} />
                    </div>
                    <p className="text-xs text-slate-300 line-clamp-1 group-hover:text-cyan-100 transition">
                      {r.user_request}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-4 text-xs font-mono">
                    <div className="text-right">
                      <span className="text-slate-200 font-semibold">
                        {summary ? `$${summary.total_usd.toFixed(4)}` : '—'}
                      </span>
                      <p className="text-[9px] text-slate-500">
                        {summary
                          ? `${(summary.total_prompt_tokens + summary.total_completion_tokens).toLocaleString()} tokens`
                          : 'Pending'}
                      </p>
                    </div>
                    <MoveUpRight className="h-3.5 w-3.5 text-slate-600 group-hover:text-cyan-300 transition" />
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}
