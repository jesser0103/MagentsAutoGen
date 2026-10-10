'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { WorkflowEvent } from '@/lib/types';
import type { EventStreamState } from '@/hooks/useEventStream';
import { mergeWorkflowEvents } from '@/lib/events';
import {
  Terminal,
  ChevronUp,
  ChevronDown,
  Trash2,
  Pause,
  Play,
} from 'lucide-react';

interface TerminalConsoleProps {
  events: WorkflowEvent[];
  runEvents: WorkflowEvent[];
  connected: boolean;
  connectionState: EventStreamState;
}

function getEventColor(type: string): string {
  switch (type) {
    case 'input_screened':
      return 'text-blue-400';
    case 'context_bounded':
      return 'text-amber-400';
    case 'rules_retrieved':
      return 'text-purple-400';
    case 'artifact_generated':
      return 'text-emerald-400';
    case 'scan_completed':
      return 'text-cyan-400';
    case 'review_completed':
      return 'text-indigo-400';
    case 'sandbox_completed':
      return 'text-teal-400';
    case 'blocked':
      return 'text-red-400';
    case 'completed':
      return 'text-emerald-400';
    default:
      return 'text-slate-400';
  }
}

export function TerminalConsole({ events, runEvents, connected, connectionState }: TerminalConsoleProps) {
  const [expanded, setExpanded] = useState(false);
  const [paused, setPaused] = useState(false);
  const [height, setHeight] = useState(160);
  const bottomRef = useRef<HTMLDivElement>(null);
  const resizeRef = useRef<HTMLDivElement>(null);

  const allEvents = useMemo(() => mergeWorkflowEvents(runEvents, events), [events, runEvents]);

  useEffect(() => {
    if (!paused && bottomRef.current && expanded) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [allEvents, paused, expanded]);

  useEffect(() => {
    const el = resizeRef.current;
    if (!el) return;
    let startY = 0;
    let startH = 0;

    const onMove = (e: MouseEvent) => {
      const delta = startY - e.clientY;
      setHeight(Math.min(Math.max(startH + delta, 120), 600));
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    const onDown = (e: MouseEvent) => {
      startY = e.clientY;
      startH = height;
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    };

    el.addEventListener('mousedown', onDown);
    return () => el.removeEventListener('mousedown', onDown);
  }, [height]);

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-40 border-t border-border/40 bg-[#070a12]/95 backdrop-blur-xl transition-transform duration-300',
        expanded ? 'translate-y-0' : 'translate-y-[calc(100%-40px)]'
      )}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 h-10 bg-[#0d1117]/80 border-b border-border/20 cursor-pointer select-none">
        <div
          className="flex items-center gap-2 flex-1"
          onClick={() => setExpanded((v) => !v)}
        >
          <Terminal className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-xs font-medium text-slate-300">Event Stream</span>
          {connected && (
            <span className="flex items-center gap-1 text-[10px] text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LIVE
            </span>
          )}
          {connectionState === 'reconnecting' && (
            <span className="flex items-center gap-1 text-[10px] text-amber-300">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-300 animate-pulse" />
              RECONNECTING…
            </span>
          )}
          <span className="text-[10px] text-muted-foreground font-mono ml-2">
            {allEvents.length} events
          </span>
        </div>
        <div className="flex items-center gap-1">
          {expanded && (
            <>
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                onClick={(e) => {
                  e.stopPropagation();
                  setPaused((p) => !p);
                }}
              >
                {paused ? (
                  <Play className="w-3 h-3 text-slate-400" />
                ) : (
                  <Pause className="w-3 h-3 text-slate-400" />
                )}
              </Button>
            </>
          )}
          <Button
            size="icon"
            variant="ghost"
            className="h-6 w-6"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => !v);
            }}
          >
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
            )}
          </Button>
        </div>
      </div>

      {/* Resize handle */}
      {expanded && (
        <div
          ref={resizeRef}
          className="h-1 cursor-ns-resize hover:bg-primary/20 transition-colors"
        />
      )}

      {/* Terminal content */}
      {expanded && (
        <div
          className="terminal-scroll overflow-y-auto px-4 py-2 font-mono text-[11px] leading-5"
          style={{ height }}
        >
          {allEvents.length === 0 ? (
            <div className="text-slate-500 italic">Waiting for telemetry…</div>
          ) : (
            allEvents.map((evt, i) => (
              <div key={i} className="flex gap-2 py-0.5 hover:bg-white/[0.02] rounded">
                <span className="text-slate-600 shrink-0">
                  {new Date(evt.created_at).toLocaleTimeString('en-US', {
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                  })}
                </span>
                <span className={cn('shrink-0 font-semibold w-20 truncate', getEventColor(evt.event_type))}>
                  [{evt.agent}]
                </span>
                <span className="text-slate-300 break-all">{evt.message}</span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
