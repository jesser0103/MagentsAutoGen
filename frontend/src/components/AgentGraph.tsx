'use client';

import { useCallback, useMemo, useState } from 'react';
import { ReactFlow, Background, Controls, type Edge, type Node, Position } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { AgentInspector } from './AgentInspector';
import { Bot, Braces, CheckCircle2, Container, Fingerprint, Shield } from 'lucide-react';

interface AgentGraphProps {
  status: string;
  events?: { agent: string; message: string; event_type: string; created_at: string }[];
}

const NODE_ORDER = ['input', 'planner', 'approval', 'coder', 'reviewer', 'docker'];
const NODE_META = {
  input: { label: 'Input shield', role: 'GUARD', icon: Shield, color: '#67e8f9' },
  planner: { label: 'Planner', role: 'AGENT 01', icon: Bot, color: '#c4b5fd' },
  approval: { label: 'Approval', role: 'HUMAN GATE', icon: Fingerprint, color: '#fcd34d' },
  coder: { label: 'Coder', role: 'AGENT 02', icon: Braces, color: '#67e8f9' },
  reviewer: { label: 'Reviewer', role: 'AGENT 03', icon: CheckCircle2, color: '#6ee7b7' },
  docker: { label: 'Sandbox', role: 'ISOLATED', icon: Container, color: '#7dd3fc' },
} as const;

const DESCRIPTIONS: Record<string, string> = {
  input: 'Screens requests for safety, policy compliance, and prompt-injection attempts.',
  planner: 'Builds a language-aware implementation plan and identifies open questions.',
  approval: 'Enforces the human-in-the-loop checkpoint before code generation.',
  coder: 'Generates infrastructure-as-code or Python from the approved plan.',
  reviewer: 'Evaluates security, policy alignment, and implementation quality.',
  docker: 'Validates artifacts inside a network-isolated, read-only container.',
};

const ACTIVE_MAP: Record<string, string> = {
  planning: 'planner', needs_clarification: 'planner', awaiting_approval: 'approval', coding: 'coder', auto_fixing: 'coder',
  scanning: 'coder', reviewing: 'reviewer', approved: 'reviewer', sandboxing: 'docker',
  completed: 'docker', needs_manual_intervention: 'docker', blocked: 'input', failed: 'input',
};
const DONE_THRESHOLD: Record<string, number> = {
  planning: 1, needs_clarification: 1, awaiting_approval: 2, coding: 3, auto_fixing: 3, scanning: 3,
  reviewing: 4, approved: 5, sandboxing: 5, completed: 6, needs_manual_intervention: 5,
  blocked: 0, failed: 0, submitted: 0,
};

export function AgentGraph({ status, events = [] }: AgentGraphProps) {
  const [inspectorAgent, setInspectorAgent] = useState<string | null>(null);
  const active = ACTIVE_MAP[status] || '';
  const activeThreshold = DONE_THRESHOLD[status] ?? 0;
  const openInspector = useCallback((id: string) => setInspectorAgent(id), []);

  const agentEvents = useMemo(() => {
    const grouped: Record<string, string[]> = {};
    events.forEach((event) => {
      const key = event.agent?.toLowerCase() || '';
      grouped[key] = [...(grouped[key] || []), event.message];
    });
    return grouped;
  }, [events]);

  const nodes: Node[] = useMemo(() => NODE_ORDER.map((id, index) => {
    const meta = NODE_META[id as keyof typeof NODE_META];
    const Icon = meta.icon;
    const done = index < activeThreshold;
    const isActive = id === active;
    return {
      id,
      position: { x: index * 188, y: index % 2 === 0 ? 12 : 0 },
      data: {
        label: (
          <div className="flex items-center gap-2.5 text-left">
            <div className="grid h-8 w-8 place-items-center rounded-lg" style={{ background: `${meta.color}12` }}>
              <Icon size={15} style={{ color: meta.color }} />
            </div>
            <div><div className="text-[9px] font-medium tracking-wide text-slate-100">{meta.label}</div><div className="mt-0.5 font-mono text-[7px] tracking-[0.16em] text-slate-500">{done ? 'COMPLETE' : isActive ? 'PROCESSING' : meta.role}</div></div>
          </div>
        ),
      },
      style: {
        background: done ? 'rgba(16,185,129,0.055)' : isActive ? 'rgba(34,211,238,0.065)' : 'rgba(10,15,28,0.88)',
        border: `1px solid ${done ? 'rgba(52,211,153,0.35)' : isActive ? 'rgba(103,232,249,0.45)' : 'rgba(255,255,255,0.08)'}`,
        borderRadius: 14, padding: '11px', width: 152,
        boxShadow: isActive ? '0 0 34px rgba(34,211,238,0.14), inset 0 1px 0 rgba(255,255,255,0.04)' : 'inset 0 1px 0 rgba(255,255,255,0.025)',
        cursor: 'pointer', transition: 'all 0.4s ease',
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  }), [active, activeThreshold]);

  const edges: Edge[] = useMemo(() => NODE_ORDER.slice(0, -1).map((source, index) => {
    const target = NODE_ORDER[index + 1];
    const energized = active === target;
    return {
      id: `${source}-${target}`, source, target, animated: energized,
      style: { stroke: energized ? '#67e8f9' : index < activeThreshold - 1 ? '#34d399' : '#1e293b', strokeWidth: energized ? 2 : 1.4 },
    };
  }), [active, activeThreshold]);

  const selectedEvents = inspectorAgent ? agentEvents[inspectorAgent] || [] : [];
  return (
    <>
      <div className="scanline cyber-grid h-[230px] w-full overflow-hidden rounded-2xl border border-white/[0.07] bg-[#070b15]/75 shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]">
        <ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.5} maxZoom={1.4} proOptions={{ hideAttribution: true }} onNodeClick={(_, node) => openInspector(node.id)}>
          <Background gap={28} size={0.7} color="rgba(103,232,249,0.12)" />
          <Controls showInteractive={false} className="!overflow-hidden !rounded-lg !border !border-white/10 !bg-[#080d18] !shadow-none [&>button]:!border-white/10 [&>button]:!bg-transparent [&>button]:!fill-slate-500" />
        </ReactFlow>
      </div>
      <AgentInspector
        agentId={inspectorAgent || ''}
        agentLabel={inspectorAgent ? NODE_META[inspectorAgent as keyof typeof NODE_META]?.label : ''}
        isOpen={Boolean(inspectorAgent)}
        onClose={() => setInspectorAgent(null)}
        systemPrompt={DESCRIPTIONS[inspectorAgent || '']}
        inputs={selectedEvents.slice(0, 5).join('\n\n')}
        outputs={selectedEvents.slice(-5).join('\n\n')}
      />
    </>
  );
}
