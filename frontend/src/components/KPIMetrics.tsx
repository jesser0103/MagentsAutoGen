'use client';

import type { WorkflowRun, FinOpsSummary } from '@/lib/types';
import { cn } from '@/lib/utils';
import { CircleDollarSign, Gauge, RotateCcw, ShieldCheck } from 'lucide-react';

interface KPIMetricsProps {
  run: WorkflowRun;
  finops?: FinOpsSummary | null;
}

export function KPIMetrics({ run, finops }: KPIMetricsProps) {
  const criticalFindings = run.scans.reduce(
    (total, scan) => total + scan.findings.filter((finding) => finding.severity === 'critical').length,
    0
  );
  const totalTokens = finops ? finops.total_prompt_tokens + finops.total_completion_tokens : 0;

  const cards = [
    {
      label: 'Estimated cost',
      value: finops ? `$${finops.total_usd.toFixed(5)}` : '—',
      detail: 'Live FinOps estimate',
      icon: CircleDollarSign,
      accent: 'text-cyan-300',
      bars: [28, 45, 38, 64, 52, 76, 68],
    },
    {
      label: 'Token volume',
      value: totalTokens ? totalTokens.toLocaleString() : '—',
      detail: finops ? `${finops.total_prompt_tokens.toLocaleString()} in · ${finops.total_completion_tokens.toLocaleString()} out` : 'Awaiting model usage',
      icon: Gauge,
      accent: 'text-violet-300',
      bars: [22, 34, 52, 42, 72, 63, 88],
    },
    {
      label: 'Critical findings',
      value: String(criticalFindings),
      detail: criticalFindings ? 'Action required' : 'Security baseline clean',
      icon: ShieldCheck,
      accent: criticalFindings ? 'text-red-300' : 'text-emerald-300',
      bars: criticalFindings ? [75, 62, 84, 60, 92, 78, 88] : [18, 14, 12, 8, 10, 6, 4],
      alert: criticalFindings > 0,
    },
    {
      label: 'Review cycles',
      value: `${run.reviews.length} / 5`,
      detail: `${Math.max(0, 5 - run.reviews.length)} iterations available`,
      icon: RotateCcw,
      accent: 'text-sky-300',
      bars: [25, 25, 42, 42, 58, 58, Math.max(18, run.reviews.length * 18)],
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-4">
      {cards.map(({ label, value, detail, icon: Icon, accent, bars, alert }) => (
        <div
          key={label}
          className={cn(
            'glass-card group relative overflow-hidden p-4 transition duration-300 hover:-translate-y-0.5 hover:border-white/[0.12]',
            alert && 'border-red-400/20 bg-red-950/10'
          )}
        >
          <div className="flex items-center justify-between">
            <p className="data-label">{label}</p>
            <Icon className={cn('h-4 w-4', accent)} />
          </div>
          <div className="mt-4 flex items-end justify-between gap-3">
            <div>
              <p className="font-mono text-xl font-semibold tracking-tight text-white">{value}</p>
              <p className="mt-1 text-[10px] text-slate-600">{detail}</p>
            </div>
            <div className="flex h-9 items-end gap-[3px] opacity-55 transition group-hover:opacity-100">
              {bars.map((height, index) => (
                <span
                  key={index}
                  className={cn('w-[3px] rounded-full bg-current', accent)}
                  style={{ height: `${height}%` }}
                />
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
