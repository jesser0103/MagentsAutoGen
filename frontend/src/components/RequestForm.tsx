'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { TemplatePanel } from '@/components/TemplatePanel';
import { AlertCircle, ArrowUpRight, BookOpen, Braces, Loader2, RotateCcw, Sparkles } from 'lucide-react';

interface RequestFormProps {
  onSubmit: (request: string) => void;
  loading: boolean;
  error?: string | null;
  initialValue?: string;
}

const MAX_INPUT_CHARACTERS = 4000;
const DRAFT_STORAGE_KEY = 'magents_request_draft';

const PROMPTS = [
  'Build a private Azure storage account with required governance tags.',
  'Create a secure Python health-check service with structured logging.',
  'Design Terraform for an isolated Azure application environment.',
];

export function RequestForm({ onSubmit, loading, error, initialValue = '' }: RequestFormProps) {
  const [request, setRequest] = useState(initialValue);
  const [mounted, setMounted] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);

  // Load saved draft on mount
  useEffect(() => {
    setMounted(true);
    try {
      const savedDraft = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (savedDraft) {
        setRequest(savedDraft);
      }
    } catch {
      // Ignore localStorage read errors
    }
  }, []);

  useEffect(() => {
    if (initialValue) handleRequestChange(initialValue);
  }, [initialValue]);

  // Update draft in localStorage whenever request changes
  const handleRequestChange = (value: string) => {
    setRequest(value);
    try {
      if (value.trim()) {
        localStorage.setItem(DRAFT_STORAGE_KEY, value);
      } else {
        localStorage.removeItem(DRAFT_STORAGE_KEY);
      }
    } catch {
      // Ignore localStorage write errors
    }
  };

  const handleSelectPrompt = (promptText: string) => {
    handleRequestChange(promptText);
  };

  const submit = () => {
    if (!request.trim() || loading) return;
    // We do NOT clear request here so user input is never lost on network or API failure.
    // Draft will be cleaned up on confirmed successful run creation.
    onSubmit(request.trim());
  };

  return (
    <div className="glass-panel panel-highlight relative overflow-hidden p-1">
      <div className="absolute inset-x-16 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/70 to-transparent" />
      <div className="rounded-[calc(var(--radius)-4px)] bg-[#070b16]/75 p-4 sm:p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-cyan-300" />
            <span className="eyebrow">Mission prompt</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowTemplates(true)}
              className="flex items-center gap-1.5 rounded-full border border-white/[0.07] bg-white/[0.025] px-2.5 py-1 text-[9px] font-medium text-slate-400 transition hover:border-cyan-300/20 hover:text-cyan-200"
            >
              <BookOpen className="h-3 w-3" /> Templates
            </button>
            <span className="font-mono text-[9px] text-slate-600">
              {mounted ? request.length.toLocaleString() : 0} / {MAX_INPUT_CHARACTERS.toLocaleString()}
            </span>
          </div>
        </div>

        <Textarea
          aria-label="Infrastructure request"
          placeholder="Describe the infrastructure, code, or security outcome you want the agent mesh to deliver…"
          value={request}
          maxLength={MAX_INPUT_CHARACTERS}
          onChange={(event) => handleRequestChange(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') submit();
          }}
          className="min-h-[148px] resize-none border-0 bg-transparent px-1 py-2 text-base leading-relaxed text-slate-100 shadow-none placeholder:text-slate-600 focus-visible:ring-0"
        />

        {error && (
          <div className="mt-3 flex items-center justify-between rounded-xl border border-red-400/25 bg-red-950/30 px-3.5 py-2.5 text-xs text-red-200 backdrop-blur-md">
            <div className="flex items-center gap-2 min-w-0 mr-3">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
              <span className="truncate">{error}</span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={submit}
              disabled={loading || !request.trim()}
              className="h-7 shrink-0 border-red-400/30 bg-red-900/30 px-2.5 text-[11px] text-red-100 hover:bg-red-900/50"
            >
              <RotateCcw className="mr-1.5 h-3 w-3" /> Retry
            </Button>
          </div>
        )}

        <div className="mt-3 flex flex-col gap-3 border-t border-white/[0.06] pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
            <Braces className="h-3.5 w-3.5 shrink-0 text-slate-600" />
            {PROMPTS.map((prompt, index) => (
              <button
                key={prompt}
                type="button"
                onClick={() => handleSelectPrompt(prompt)}
                className="shrink-0 rounded-full border border-white/[0.07] bg-white/[0.025] px-2.5 py-1 text-[9px] text-slate-500 transition hover:border-cyan-300/20 hover:text-cyan-100"
              >
                0{index + 1} {prompt.split(' ').slice(0, 3).join(' ')}…
              </button>
            ))}
          </div>
          <Button
            onClick={submit}
            disabled={!request.trim() || loading}
            className="h-11 shrink-0 rounded-xl bg-cyan-300 px-5 text-xs font-semibold text-slate-950 shadow-[0_0_28px_rgba(34,211,238,0.2)] transition-all hover:-translate-y-0.5 hover:bg-cyan-200"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Orchestrating
              </>
            ) : (
              <>
                Initialize mission <ArrowUpRight className="ml-2 h-4 w-4" />
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Template library slide-over */}
      {showTemplates && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowTemplates(false)}
          />
          <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md animate-fade-in">
            <TemplatePanel
              onSelect={(req) => { handleRequestChange(req); }}
              onClose={() => setShowTemplates(false)}
              currentRequest={request}
            />
          </div>
        </>
      )}
    </div>
  );
}
