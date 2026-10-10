'use client';

import { cn } from '@/lib/utils';
import type { WorkflowRun } from '@/lib/types';
import { AlertTriangle, ArrowRight, Bot, Check, Loader2, RotateCcw, ShieldAlert } from 'lucide-react';

interface SelfHealingPanelProps {
  run: WorkflowRun;
  maxRounds?: number;
}

/**
 * SelfHealingPanel — shown when the Coder is automatically revising its output
 * after a reviewer rejection (status: "coding" after ≥1 review exists).
 *
 * Displays:
 *  - How many review rounds have run vs. the maximum
 *  - The required_changes the reviewer flagged in the last rejection
 *  - A live pulsing indicator while the Coder agent is working
 */
export function SelfHealingPanel({ run, maxRounds = 3 }: SelfHealingPanelProps) {
  const isScannerHealing = run.status === 'auto_fixing';
  const isHealing =
    (run.status === 'coding' && run.reviews.length > 0) || isScannerHealing;
  const isScanning = run.status === 'scanning' && run.reviews.length > 0;
  const isReviewing = run.status === 'reviewing' && run.reviews.length > 0;

  const active = isHealing || isScanning || isReviewing;
  if (!active) return null;

  const roundsDone = isScannerHealing ? run.auto_fix_attempts : run.reviews.length;
  const lastReview = run.reviews[roundsDone - 1];
  const requiredChanges = lastReview?.required_changes ?? [];
  const progressPct = Math.round((roundsDone / maxRounds) * 100);

  const phaseLabel = isScannerHealing
    ? 'Coder is correcting scanner findings...'
    : isHealing
    ? 'Coder is revising the artifact…'
    : isScanning
    ? 'Re-scanning revised artifact…'
    : 'Reviewer is re-checking…';

  return (
    <div className="animate-fade-in rounded-2xl border border-amber-400/20 bg-amber-950/10 p-5 backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-amber-300/20 bg-amber-300/[0.07]">
          {isHealing ? (
            <Bot className="h-5 w-5 text-amber-200 animate-pulse" />
          ) : isScanning ? (
            <Loader2 className="h-5 w-5 text-amber-200 animate-spin" />
          ) : (
            <RotateCcw className="h-5 w-5 text-amber-200 animate-spin" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-200/70">
            Self-healing loop — round {roundsDone} / {maxRounds}
          </p>
          <h3 className="mt-1 text-sm font-semibold text-amber-50">{phaseLabel}</h3>
          <p className="mt-1 text-xs text-amber-100/50 leading-5">
            The reviewer rejected the previous artifact. The Coder is automatically incorporating the feedback below.
          </p>
        </div>
      </div>

      {/* Round progress bar */}
      <div className="mt-4 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-widest text-amber-200/50">Iteration progress</span>
          <span className="font-mono text-[10px] text-amber-300">{roundsDone}/{maxRounds}</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-400 transition-all duration-700"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="flex justify-between">
          {Array.from({ length: maxRounds }).map((_, i) => (
            <div key={i} className="flex flex-col items-center gap-1">
              <div className={cn(
                'h-3.5 w-3.5 rounded-full border transition-all',
                i < roundsDone
                  ? 'border-amber-400/60 bg-amber-400/20'
                  : i === roundsDone
                  ? 'border-amber-300/40 bg-amber-300/10 animate-pulse'
                  : 'border-white/10 bg-transparent',
              )}>
                {i < roundsDone && (
                  <Check className="h-full w-full p-0.5 text-amber-300" />
                )}
              </div>
              <span className="text-[8px] uppercase tracking-wider text-amber-200/30">R{i + 1}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Reviewer's required changes from last rejection */}
      {requiredChanges.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-400/10 bg-black/10 p-4">
          <div className="mb-2 flex items-center gap-1.5">
            <ShieldAlert className="h-3.5 w-3.5 text-amber-300" />
            <p className="text-[10px] font-semibold uppercase tracking-widest text-amber-300/70">
              Reviewer flagged {requiredChanges.length} required change{requiredChanges.length !== 1 ? 's' : ''}
            </p>
          </div>
          <ul className="space-y-1.5">
            {requiredChanges.map((change, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-amber-100/60">
                <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-amber-400/50" />
                <span>{change}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Warning when approaching limit */}
      {roundsDone >= maxRounds - 1 && roundsDone < maxRounds && (
        <div className="mt-3 flex items-center gap-2 rounded-xl border border-orange-400/20 bg-orange-950/20 px-3 py-2 text-xs text-orange-300">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          Final revision attempt — if this round fails, the mission will require manual intervention.
        </div>
      )}
    </div>
  );
}
