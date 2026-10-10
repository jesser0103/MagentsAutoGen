'use client';

import { cn } from '@/lib/utils';
import { Check, Code2, Flag, Library, ScanLine, Shield } from 'lucide-react';

const STAGES = [
  { id: 'input_screening', label: 'Shield', icon: Shield },
  { id: 'rag_ingestion', label: 'Context', icon: Library },
  { id: 'plan_approval', label: 'Approval', icon: Flag },
  { id: 'code_execution', label: 'Build', icon: Code2 },
  { id: 'security_scanning', label: 'Validate', icon: ScanLine },
  { id: 'complete', label: 'Complete', icon: Check },
];

const STATUS_TO_STAGE: Record<string, string> = {
  submitted: 'input_screening', planning: 'rag_ingestion', needs_clarification: 'plan_approval',
  awaiting_approval: 'plan_approval', coding: 'code_execution', auto_fixing: 'code_execution', scanning: 'code_execution',
  reviewing: 'security_scanning', approved: 'security_scanning', sandboxing: 'security_scanning',
  completed: 'complete', needs_manual_intervention: 'security_scanning', blocked: 'input_screening', failed: 'input_screening',
};

export function StageProgress({ status }: { status: string }) {
  const currentIndex = Math.max(0, STAGES.findIndex((stage) => stage.id === (STATUS_TO_STAGE[status] || 'input_screening')));
  const progress = ((currentIndex + 1) / STAGES.length) * 100;
  const terminalError = status === 'blocked' || status === 'failed';

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div><p className="data-label">Mission sequence</p><p className="mt-1 text-xs text-slate-400">Stage {currentIndex + 1} of {STAGES.length}</p></div>
        <span className="font-mono text-xs text-cyan-300">{Math.round(progress)}%</span>
      </div>
      <div className="relative">
        <div className="absolute left-5 right-5 top-4 h-px bg-white/[0.07]" />
        <div className="absolute left-5 right-5 top-4 h-px">
          <div
            className={cn('h-full transition-all duration-700', terminalError ? 'bg-red-400' : status === 'completed' ? 'bg-emerald-400' : 'bg-gradient-to-r from-cyan-400 to-violet-400')}
            style={{ width: `${Math.max(0, (currentIndex / (STAGES.length - 1)) * 100)}%` }}
          />
        </div>
        <div className="relative grid grid-cols-6">
          {STAGES.map(({ id, label, icon: Icon }, index) => {
            const done = index < currentIndex || status === 'completed';
            const active = index === currentIndex && status !== 'completed';
            return (
              <div key={id} className="flex min-w-0 flex-col items-center gap-2">
                <div className={cn(
                  'grid h-8 w-8 place-items-center rounded-full border bg-[#080c17] transition-all duration-500',
                  done ? 'border-emerald-400/50 text-emerald-300' : active ? 'border-cyan-300/60 text-cyan-200 shadow-[0_0_24px_rgba(34,211,238,0.22)]' : 'border-white/[0.08] text-slate-700'
                )}>
                  {done ? <Check className="h-3.5 w-3.5" /> : <Icon className="h-3.5 w-3.5" />}
                </div>
                <span className={cn('hidden text-[9px] uppercase tracking-[0.11em] sm:block', active ? 'text-slate-200' : 'text-slate-600')}>{label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
