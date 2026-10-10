'use client';

import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { updatePlan } from '@/lib/api';
import type { Plan, PlanStep } from '@/lib/types';
import { Check, Edit3, GripVertical, Loader2, RotateCcw, Save, X } from 'lucide-react';

interface PlanEditorProps {
  plan: Plan;
  runId: string;
  editable: boolean; // only true when status === 'awaiting_approval'
  onPlanSaved?: (updated: Plan) => void;
}

/**
 * PlanEditor — inline editor for the execution plan steps shown before approval.
 *
 * When editable=true (status awaiting_approval):
 *   - Click any step description to edit it in-place
 *   - Click the plan summary to edit it
 *   - Save sends PATCH /api/runs/{runId}/plan
 *   - Reset reverts to the original server plan
 *
 * When editable=false (post-approval / coding in progress):
 *   - Renders a read-only styled list identical to the previous static display
 */
export function PlanEditor({ plan, runId, editable, onPlanSaved }: PlanEditorProps) {
  const [draft, setDraft] = useState<Plan>(() => deepClone(plan));
  const [editingStep, setEditingStep] = useState<number | null>(null);
  const [editingSummary, setEditingSummary] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  // Keep draft in sync if the parent receives a new plan (e.g. after re-plan)
  useEffect(() => {
    setDraft(deepClone(plan));
    setDirty(false);
    setEditingStep(null);
    setEditingSummary(false);
  }, [plan]);

  const updateStep = (index: number, description: string) => {
    setDraft((prev) => ({
      ...prev,
      steps: prev.steps.map((s, i) =>
        i === index ? { ...s, description } : s,
      ) as PlanStep[],
    }));
    setDirty(true);
  };

  const updateSummary = (summary: string) => {
    setDraft((prev) => ({ ...prev, summary }));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updatePlan(runId, draft);
      setDraft(deepClone(updated));
      setDirty(false);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
      onPlanSaved?.(updated);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Could not save plan.');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setDraft(deepClone(plan));
    setDirty(false);
    setEditingStep(null);
    setEditingSummary(false);
    setSaveError(null);
  };

  return (
    <div className="glass-card panel-highlight p-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Approved intent</p>
          <h2 className="mt-1 text-sm font-semibold text-white">Execution plan</h2>
        </div>
        <div className="flex items-center gap-2">
          {editable && dirty && (
            <>
              <button
                onClick={handleReset}
                disabled={saving}
                className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.025] px-2.5 py-1.5 text-[10px] text-slate-400 hover:text-slate-200 transition-all disabled:opacity-40"
              >
                <RotateCcw className="h-3 w-3" /> Reset
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[10px] font-medium transition-all disabled:opacity-40',
                  savedFlash
                    ? 'border-emerald-400/30 bg-emerald-950/20 text-emerald-300'
                    : 'border-cyan-400/30 bg-cyan-950/20 text-cyan-300 hover:bg-cyan-950/40',
                )}
              >
                {saving ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : savedFlash ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Save className="h-3 w-3" />
                )}
                {savedFlash ? 'Saved!' : saving ? 'Saving…' : 'Save changes'}
              </button>
            </>
          )}
          {editable && !dirty && (
            <span className="flex items-center gap-1 font-mono text-[9px] text-slate-600">
              <Edit3 className="h-3 w-3" /> Click any step to edit
            </span>
          )}
          {!editable && (
            <span className="font-mono text-[9px] text-slate-600">
              {draft.steps.length} STEPS
            </span>
          )}
        </div>
      </div>

      {/* Save error */}
      {saveError && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-400/20 bg-red-950/20 px-3 py-2 text-[11px] text-red-300">
          <X className="h-3.5 w-3.5 shrink-0" />
          {saveError}
        </div>
      )}

      {/* Plan summary */}
      <div className="mt-4">
        {editable && editingSummary ? (
          <textarea
            autoFocus
            className="w-full resize-none rounded-lg border border-cyan-400/30 bg-black/20 px-3 py-2 text-sm leading-6 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-cyan-400/20"
            rows={3}
            value={draft.summary}
            onChange={(e) => updateSummary(e.target.value)}
            onBlur={() => setEditingSummary(false)}
          />
        ) : (
          <p
            onClick={() => editable && setEditingSummary(true)}
            className={cn(
              'text-sm leading-6 text-slate-300',
              editable && 'cursor-text rounded-lg px-1 py-0.5 hover:bg-white/[0.03] hover:text-white transition-all',
            )}
          >
            {draft.summary}
          </p>
        )}
      </div>

      {/* Steps */}
      <ol className="mt-4 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
        {draft.steps.map((step, index) => (
          <li
            key={index}
            className={cn(
              'group relative rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 transition-all',
              editable && editingStep !== index && 'hover:border-cyan-300/20 hover:bg-cyan-300/[0.025] cursor-pointer',
              editingStep === index && 'border-cyan-400/30 bg-cyan-950/10',
            )}
            onClick={() => editable && editingStep !== index && setEditingStep(index)}
          >
            <div className="flex items-start gap-2">
              {editable && (
                <GripVertical className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-700 opacity-0 group-hover:opacity-100 transition-opacity" />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-cyan-300">0{index + 1}</span>
                  <strong className="capitalize text-slate-200">{step.language}</strong>
                  {editable && editingStep !== index && (
                    <Edit3 className="h-2.5 w-2.5 text-slate-700 opacity-0 group-hover:opacity-100 transition-opacity" />
                  )}
                </div>
                {editable && editingStep === index ? (
                  <div className="mt-1.5">
                    <textarea
                      autoFocus
                      rows={3}
                      className="w-full resize-none rounded-md border border-cyan-400/20 bg-black/20 px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-cyan-400/20"
                      value={step.description}
                      onChange={(e) => updateStep(index, e.target.value)}
                    />
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <button
                        onClick={(e) => { e.stopPropagation(); setEditingStep(null); }}
                        className="flex items-center gap-1 rounded-md border border-emerald-400/20 bg-emerald-950/20 px-2 py-1 text-[10px] text-emerald-300 hover:bg-emerald-950/40 transition-all"
                      >
                        <Check className="h-2.5 w-2.5" /> Done
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          // Revert just this step
                          setDraft((prev) => ({
                            ...prev,
                            steps: prev.steps.map((s, i) =>
                              i === index ? { ...s, description: plan.steps[index]?.description ?? s.description } : s,
                            ) as PlanStep[],
                          }));
                          setEditingStep(null);
                        }}
                        className="flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-[10px] text-slate-500 hover:text-slate-300 transition-all"
                      >
                        <X className="h-2.5 w-2.5" /> Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="mt-1 text-slate-400 leading-5">— {step.description}</p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}
