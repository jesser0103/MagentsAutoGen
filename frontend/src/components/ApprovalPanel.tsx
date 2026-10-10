'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import type { WorkflowRun, ScanReport, ReviewResult } from '@/lib/types';
import { AlertTriangle, ArrowRight, Check, Fingerprint, Loader2, RotateCcw, ShieldCheck, RefreshCw } from 'lucide-react';

interface ApprovalPanelProps {
  run: WorkflowRun;
  onApprove: () => void;
  onReject: (feedback: string) => void;
  loading: boolean;
  isReplanning?: boolean;
  canDecide?: boolean;
}

// ---------------------------------------------------------------------------
// Risk summary helpers
// ---------------------------------------------------------------------------

function buildRiskSummary(scans: ScanReport[], reviews: ReviewResult[]): string | null {
  const parts: string[] = [];

  // Scan findings
  const allFindings = scans.flatMap((s) => s.findings);
  if (allFindings.length > 0) {
    const severities = allFindings.map((f) => f.severity.toLowerCase());
    const maxSeverity = ['critical', 'high', 'medium', 'low', 'info'].find((s) =>
      severities.includes(s),
    ) || severities[0];
    parts.push(`${allFindings.length} scan finding${allFindings.length !== 1 ? 's' : ''} (highest: ${maxSeverity})`);
  } else if (scans.length > 0) {
    parts.push('All scans clean');
  }

  // Review verdict
  const latestReview = reviews[reviews.length - 1];
  if (latestReview) {
    parts.push(`Reviewer: ${latestReview.verdict}${latestReview.required_changes.length > 0 ? ` with ${latestReview.required_changes.length} required change${latestReview.required_changes.length !== 1 ? 's' : ''}` : ''}`);
  }

  return parts.length > 0 ? parts.join(' · ') : null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CONFIRM_TIMEOUT_MS = 3_000;

export function ApprovalPanel({
  run,
  onApprove,
  onReject,
  loading,
  isReplanning = false,
  canDecide = true,
}: ApprovalPanelProps) {
  const [feedback, setFeedback] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [confirmStep, setConfirmStep] = useState(false);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset confirm state when loading finishes or status changes
  useEffect(() => {
    setConfirmStep(false);
    if (confirmTimerRef.current) {
      clearTimeout(confirmTimerRef.current);
      confirmTimerRef.current = null;
    }
  }, [run.status, loading]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    };
  }, []);

  const handleApproveClick = useCallback(() => {
    if (!confirmStep) {
      // First click — enter confirm state
      setConfirmStep(true);
      confirmTimerRef.current = setTimeout(() => {
        setConfirmStep(false);
        confirmTimerRef.current = null;
      }, CONFIRM_TIMEOUT_MS);
    } else {
      // Second click — actually approve
      if (confirmTimerRef.current) {
        clearTimeout(confirmTimerRef.current);
        confirmTimerRef.current = null;
      }
      setConfirmStep(false);
      onApprove();
    }
  }, [confirmStep, onApprove]);

  if (run.status !== 'awaiting_approval' && run.status !== 'needs_clarification' && !isReplanning) return null;

  const riskSummary = buildRiskSummary(run.scans, run.reviews);

  return (
    <section
      aria-label="Human authorization gate"
      role="region"
      className="sticky bottom-0 z-40 -mx-4 sm:-mx-6 lg:-mx-8 mt-5 rounded-t-2xl border-t border-x border-amber-300/20 bg-[#0b0f19]/95 p-5 shadow-[0_-8px_40px_rgba(251,191,36,0.08)] backdrop-blur-xl"
    >
      <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-amber-300/80 to-transparent" />

      {/* Risk summary bar */}
      {riskSummary && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2 text-[10px] text-slate-400">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-300" />
          <span className="truncate">{riskSummary}</span>
        </div>
      )}

      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex max-w-2xl items-start gap-3">
          <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl border ${isReplanning ? 'border-violet-300/20 bg-violet-300/[0.07]' : 'border-amber-300/20 bg-amber-300/[0.07]'}`}>
            {isReplanning
              ? <RefreshCw className="h-5 w-5 text-violet-200 animate-spin" />
              : <Fingerprint className="h-5 w-5 text-amber-200" />}
          </div>
          <div>
            <p className={`text-[10px] font-semibold uppercase tracking-[0.2em] ${isReplanning ? 'text-violet-200/70' : 'text-amber-200/70'}`}>
              {isReplanning ? 'Re-planning in progress' : 'Human authorization gate'}
            </p>
            <h3 className={`mt-1 text-base font-semibold ${isReplanning ? 'text-violet-50' : 'text-amber-50'}`}>
              {isReplanning
                ? 'Planner is incorporating your feedback…'
                : 'Your approval is required to continue.'}
            </h3>
            <p className={`mt-1 text-xs leading-5 ${isReplanning ? 'text-violet-100/55' : 'text-amber-100/55'}`}>
              {isReplanning
                ? 'The revised plan will appear here automatically when ready. This may take a few seconds.'
                : 'Authorizing will start the Coder agent and generate production artifacts. The plan is frozen until you decide.'}
            </p>
          </div>
        </div>
        {isReplanning ? (
          <div className="flex shrink-0 items-center gap-2 rounded-xl border border-violet-400/20 bg-violet-950/20 px-4 py-2.5 text-xs text-violet-300">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Waiting for revised plan…
          </div>
        ) : (
          <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
            <Button
              aria-label={confirmStep ? 'Click again to confirm authorization' : 'Authorize build'}
              onClick={handleApproveClick}
              disabled={loading || !canDecide}
              className={`h-10 rounded-xl px-4 text-xs font-semibold transition-all duration-200 ${
                confirmStep
                  ? 'animate-pulse bg-emerald-400 text-emerald-950 ring-2 ring-emerald-300/50 hover:bg-emerald-300'
                  : 'bg-emerald-300 text-emerald-950 hover:bg-emerald-200'
              }`}
            >
              {loading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : confirmStep ? (
                <Check className="mr-2 h-4 w-4" />
              ) : (
                <ShieldCheck className="mr-2 h-4 w-4" />
              )}
              {confirmStep ? 'Confirm authorization' : 'Authorize build'}
              {!confirmStep && <ArrowRight className="ml-2 h-3.5 w-3.5" />}
            </Button>
            <Button
              aria-label="Request revision"
              aria-expanded={showReject}
              variant="outline"
              onClick={() => setShowReject((value) => !value)}
              disabled={loading || !canDecide}
              className="h-10 rounded-xl border-white/10 bg-white/[0.025] text-xs text-slate-300"
            >
              <RotateCcw className="mr-2 h-3.5 w-3.5" /> Request revision
            </Button>
          </div>
        )}
      </div>

      {!isReplanning && !canDecide && (
        <p className="mt-3 rounded-lg border border-amber-300/15 bg-amber-300/[0.04] px-3 py-2 text-xs text-amber-100/75">
          A separate user with the approver role must approve or request changes to this plan.
        </p>
      )}

      {!isReplanning && run.status === 'needs_clarification' && (run.plan?.open_questions.length ?? 0) > 0 && (
        <div className="mt-4 rounded-xl border border-white/[0.06] bg-black/10 p-4" role="region" aria-label="Planner clarification questions">
          <p className="data-label">Planner questions</p>
          <ul className="mt-2 space-y-1 text-xs text-slate-300">{run.plan?.open_questions.map((question, index) => <li key={index}>0{index + 1} / {question}</li>)}</ul>
        </div>
      )}

      {!isReplanning && showReject && (
        <div className="mt-4 animate-fade-in space-y-3 border-t border-white/[0.07] pt-4">
          <Textarea aria-label="Describe exactly what the planner must revise" placeholder="Describe exactly what the planner must revise…" value={feedback} onChange={(event) => setFeedback(event.target.value)} className="min-h-[90px] border-white/10 bg-black/15" />
          <Button aria-label="Submit revision request" variant="destructive" size="sm" disabled={!feedback.trim() || loading} onClick={() => { onReject(feedback); setFeedback(''); setShowReject(false); }}>Submit revision request</Button>
        </div>
      )}
    </section>
  );
}
