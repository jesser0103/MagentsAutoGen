'use client';

import { RequestForm } from '@/components/RequestForm';
import { RunHistory } from '@/components/RunHistory';
import type { RunHistoryEntry } from '@/lib/runHistory';
import {
  Activity,
  ArrowRight,
  Bot,
  Boxes,
  Braces,
  CheckCircle2,
  Fingerprint,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

interface DashboardOverviewProps {
  onSubmit: (request: string) => void;
  onSelectRun: (runId: string) => void;
  loading: boolean;
  error?: string | null;
  recentRuns: RunHistoryEntry[];
}

const CAPABILITIES = [
  { icon: Braces, label: 'Code generation', value: 'Python + Terraform', color: 'text-cyan-300' },
  { icon: ShieldCheck, label: 'Security gates', value: 'Policy + SAST + Sandbox', color: 'text-emerald-300' },
  { icon: Fingerprint, label: 'Human control', value: 'Approval enforced', color: 'text-violet-300' },
];

export function DashboardOverview({
  onSubmit,
  onSelectRun,
  loading,
  error,
  recentRuns,
}: DashboardOverviewProps) {
  return (
    <div className="animate-fade-in space-y-6 pb-20">
      <section className="grid min-h-[520px] items-center gap-10 py-8 lg:grid-cols-[1.08fr_0.92fr] lg:py-14">
        <div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-3 py-1.5">
            <span className="status-dot" />
            <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-cyan-100/80">
              Agent mesh ready
            </span>
          </div>
          <h2 className="max-w-3xl text-balance text-4xl font-semibold leading-[1.05] tracking-[-0.045em] text-white sm:text-5xl xl:text-6xl">
            Cloud engineering at the speed of{' '}
            <span className="gradient-text">thought.</span>
          </h2>
          <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
            A governed multi-agent control plane that plans, writes, reviews, scans, and validates
            production-ready infrastructure—while you stay in command.
          </p>
          <div className="mt-8 max-w-3xl">
            <RequestForm onSubmit={onSubmit} loading={loading} error={error} />
          </div>
        </div>

        <div className="relative mx-auto hidden h-[480px] w-full max-w-[520px] place-items-center lg:grid">
          <div className="absolute inset-10 rounded-full border border-cyan-300/[0.08]" />
          <div className="absolute inset-20 animate-orbit rounded-full border border-dashed border-violet-400/15" />
          <div className="absolute inset-32 rounded-full border border-cyan-300/[0.12] bg-cyan-300/[0.015] shadow-[inset_0_0_80px_rgba(34,211,238,0.04)]" />
          <div className="absolute inset-[39%] animate-pulse-glow rounded-3xl border border-cyan-300/30 bg-[#091322] shadow-[0_0_60px_rgba(34,211,238,0.15)]">
            <div className="grid h-full place-items-center">
              <Bot className="h-10 w-10 text-cyan-200" />
            </div>
          </div>
          {[
            ['Planner', 'left-[3%] top-[22%]', Sparkles, 'text-violet-300'],
            ['Coder', 'right-[2%] top-[20%]', Braces, 'text-cyan-300'],
            ['Reviewer', 'bottom-[16%] right-[6%]', CheckCircle2, 'text-emerald-300'],
            ['Policy RAG', 'bottom-[14%] left-[4%]', Boxes, 'text-sky-300'],
          ].map(([label, position, Icon, color]) => {
            const NodeIcon = Icon as typeof Bot;
            return (
              <div key={label as string} className={`absolute ${position} animate-float-slow`}>
                <div className="glass-card flex items-center gap-3 px-3.5 py-3">
                  <div className="grid h-8 w-8 place-items-center rounded-lg bg-white/[0.04]">
                    <NodeIcon className={`h-4 w-4 ${color}`} />
                  </div>
                  <div>
                    <p className="text-[10px] font-medium text-slate-200">{label as string}</p>
                    <p className="mt-0.5 font-mono text-[8px] uppercase tracking-wider text-emerald-400">Online</p>
                  </div>
                </div>
              </div>
            );
          })}
          <div className="absolute inset-x-20 bottom-0 flex items-center justify-center gap-2 font-mono text-[9px] uppercase tracking-[0.2em] text-slate-600">
            <Activity className="h-3 w-3 text-cyan-400" /> Live orchestration fabric
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {CAPABILITIES.map(({ icon: Icon, label, value, color }, index) => (
          <div key={label} className="glass-card group panel-highlight p-5 transition duration-300 hover:-translate-y-1 hover:border-white/[0.12]">
            <div className="flex items-start justify-between">
              <div className="grid h-9 w-9 place-items-center rounded-xl border border-white/[0.07] bg-white/[0.035]">
                <Icon className={`h-4 w-4 ${color}`} />
              </div>
              <span className="font-mono text-[9px] text-slate-700">0{index + 1}</span>
            </div>
            <p className="mt-6 data-label">{label}</p>
            <div className="mt-1 flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-200">{value}</p>
              <ArrowRight className="h-3.5 w-3.5 text-slate-700 transition group-hover:translate-x-1 group-hover:text-cyan-300" />
            </div>
          </div>
        ))}
      </section>

      {recentRuns.length > 0 && (
        <section className="grid gap-4 lg:grid-cols-[1fr_2fr]">
          <div className="glass-card p-6">
            <p className="eyebrow">Operations archive</p>
            <h3 className="mt-3 text-xl font-semibold tracking-tight text-white">Resume a mission.</h3>
            <p className="mt-2 text-xs leading-5 text-slate-500">Select a recent workflow to reopen its artifacts, security evidence, and cost telemetry.</p>
          </div>
          <RunHistory runs={recentRuns} activeRunId={null} onSelect={onSelectRun} />
        </section>
      )}
    </div>
  );
}
