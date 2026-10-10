'use client';

import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { X, Bot, MessageSquare, Code, Eye } from 'lucide-react';

interface AgentInspectorProps {
  agentId: string;
  agentLabel: string;
  isOpen: boolean;
  onClose: () => void;
  systemPrompt?: string;
  inputs?: string;
  outputs?: string;
}

const TABS = ['prompt', 'inputs', 'outputs'] as const;
type TabKey = (typeof TABS)[number];

const TAB_META: Record<TabKey, { icon: typeof Eye; label: string }> = {
  prompt: { icon: Eye, label: 'System Prompt' },
  inputs: { icon: MessageSquare, label: 'Inputs' },
  outputs: { icon: Code, label: 'Outputs' },
};

export function AgentInspector({
  agentId,
  agentLabel,
  isOpen,
  onClose,
  systemPrompt,
  inputs,
  outputs,
}: AgentInspectorProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('prompt');
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const headingId = useId();
  const tabBaseId = useId();

  // -------------------------------------------------------------------
  // Focus management: trap focus inside the dialog, restore on close
  // -------------------------------------------------------------------

  // Capture the element that opened the dialog so we can restore focus later
  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement;
    }
  }, [isOpen]);

  // Move focus into the dialog once it mounts
  useEffect(() => {
    if (!isOpen || !dialogRef.current) return;

    // Focus the close button (or first focusable) so keyboard users land inside
    const firstFocusable = dialogRef.current.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus();

    // Restore focus on unmount / close
    return () => {
      previousFocusRef.current?.focus();
    };
  }, [isOpen]);

  // -------------------------------------------------------------------
  // Keyboard: Escape to close + focus trap on Tab
  // -------------------------------------------------------------------

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
        return;
      }

      if (event.key === 'Tab' && dialogRef.current) {
        const focusable = Array.from(
          dialogRef.current.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
          ),
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    },
    [onClose],
  );

  // -------------------------------------------------------------------
  // Arrow-key navigation for internal tabs
  // -------------------------------------------------------------------

  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>) => {
      const idx = TABS.indexOf(activeTab);
      let next: number | null = null;

      switch (event.key) {
        case 'ArrowRight':
          next = idx < TABS.length - 1 ? idx + 1 : 0;
          break;
        case 'ArrowLeft':
          next = idx > 0 ? idx - 1 : TABS.length - 1;
          break;
        case 'Home':
          next = 0;
          break;
        case 'End':
          next = TABS.length - 1;
          break;
        default:
          return;
      }

      event.preventDefault();
      setActiveTab(TABS[next]);

      // Move focus to the newly active tab trigger
      const container = event.currentTarget.parentElement;
      const buttons = container?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
      buttons?.[next]?.focus();
    },
    [activeTab],
  );

  if (!isOpen) return null;

  const tabClass = (tab: TabKey) =>
    cn(
      'text-[10px] uppercase tracking-wider px-2.5 py-1.5 rounded-md transition-colors font-medium',
      activeTab === tab
        ? 'bg-primary/20 text-primary'
        : 'text-muted-foreground hover:text-foreground hover:bg-white/5',
    );

  const panelContent: Record<TabKey, { heading: string; body: string }> = {
    prompt: { heading: 'System Prompt', body: systemPrompt || 'No system prompt available for this agent.' },
    inputs: { heading: 'Agent Inputs', body: inputs || 'No input data captured for this agent.' },
    outputs: { heading: 'Agent Outputs', body: outputs || 'No output data captured for this agent.' },
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={headingId}
      onKeyDown={handleKeyDown}
      ref={dialogRef}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <div className="relative w-full sm:max-w-lg bg-[#0b0f19] border border-border/50 rounded-t-xl sm:rounded-xl shadow-2xl overflow-hidden animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/30">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-primary" />
            </div>
            <div>
              <h3 id={headingId} className="text-sm font-semibold">{agentLabel}</h3>
              <p className="text-[10px] text-muted-foreground font-mono">{agentId}</p>
            </div>
          </div>
          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={onClose} aria-label="Close inspector">
            <X className="w-3.5 h-3.5 text-muted-foreground" />
          </Button>
        </div>

        {/* Tabs — WAI-ARIA tab pattern */}
        <div className="flex items-center gap-1 px-3 pt-3" role="tablist" aria-label="Agent inspector views">
          {TABS.map((tab) => {
            const { icon: Icon, label } = TAB_META[tab];
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                id={`${tabBaseId}-tab-${tab}`}
                role="tab"
                type="button"
                aria-selected={isActive}
                aria-controls={`${tabBaseId}-panel-${tab}`}
                tabIndex={isActive ? 0 : -1}
                className={tabClass(tab)}
                onClick={() => setActiveTab(tab)}
                onKeyDown={handleTabKeyDown}
              >
                <Icon className="w-3 h-3 inline mr-1" /> {label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div
          id={`${tabBaseId}-panel-${activeTab}`}
          role="tabpanel"
          aria-labelledby={`${tabBaseId}-tab-${activeTab}`}
          tabIndex={0}
          className="p-4 max-h-[60vh] overflow-y-auto"
        >
          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
              {panelContent[activeTab].heading}
            </p>
            <pre className="text-xs font-mono bg-[#0d1117] p-3 rounded-lg border border-white/5 text-slate-300 whitespace-pre-wrap leading-relaxed">
              {panelContent[activeTab].body}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
