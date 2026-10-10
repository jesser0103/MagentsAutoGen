'use client';

import type { RunHistoryEntry } from '@/lib/runHistory';
import { StatusBadge } from '@/components/StatusBadge';
import { History, MoveUpRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RunHistoryProps {
  runs: RunHistoryEntry[];
  activeRunId: string | null;
  onSelect: (runId: string) => void;
}

export function RunHistory({ runs, activeRunId, onSelect }: RunHistoryProps) {
  return (
    <div className="glass-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2"><History className="h-3.5 w-3.5 text-slate-500" /><p className="data-label">Mission history</p></div>
        <span className="font-mono text-[9px] text-slate-700">{runs.length}</span>
      </div>
      {runs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/[0.07] px-3 py-6 text-center"><p className="text-[10px] text-slate-600">No local missions yet</p></div>
      ) : (
        <div className="terminal-scroll max-h-[300px] space-y-1.5 overflow-y-auto pr-1">
          {runs.map((run) => (
            <button key={run.run_id} onClick={() => onSelect(run.run_id)} className={cn('group w-full rounded-xl border px-3 py-2.5 text-left transition', activeRunId === run.run_id ? 'border-cyan-300/20 bg-cyan-300/[0.05]' : 'border-transparent bg-white/[0.018] hover:border-white/[0.07] hover:bg-white/[0.035]')}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[9px] uppercase tracking-wider text-slate-600">{run.run_id.slice(0, 8)}</span>
                <div className="flex items-center gap-2">
                  {run.status && <StatusBadge status={run.status} />}
                  <MoveUpRight className="h-3 w-3 text-slate-700 transition group-hover:text-cyan-300" />
                </div>
              </div>
              <p className="mt-1.5 line-clamp-2 text-[10px] leading-4 text-slate-400">{run.user_request}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
