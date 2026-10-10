'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { AppNav } from '@/components/AppNav';
import { AgentInspector } from '@/components/AgentInspector';
import { Button } from '@/components/ui/button';
import {
  Activity,
  Bot,
  Boxes,
  Braces,
  CheckCircle2,
  Code,
  Eye,
  Layers,
  Lock,
  MessageSquare,
  Shield,
  Sparkles,
  Zap,
} from 'lucide-react';

const PROVIDER_MODE = process.env.NEXT_PUBLIC_PROVIDER_MODE || 'demo';

interface AgentCardData {
  id: string;
  label: string;
  role: string;
  description: string;
  icon: typeof Bot;
  accent: string;
  status: string;
  model: string;
  systemPrompt: string;
  capabilities: string[];
}

const AGENTS: AgentCardData[] = [
  {
    id: 'agent-planner',
    label: 'Planner Agent',
    role: 'Decomposition & Strategy',
    description: 'Analyzes user prompts, assesses cloud requirements, identifies dependencies, and structures an approval-gated step-by-step plan.',
    icon: Sparkles,
    accent: 'text-violet-300',
    status: 'Online',
    model: 'GPT-4o',
    systemPrompt: `You are the lead Cloud Infrastructure Architect and Planner Agent.
Your job is to break down complex cloud and DevOps engineering requests into discrete, sequential, executable steps.
Always specify exact cloud resource targets, required IAM roles, governance tags, and network isolation requirements.
Do not execute or generate code directly; your output must be a structured JSON Plan with clear steps and any open clarification questions.`,
    capabilities: ['Intent Screening', 'Step Decomposition', 'Clarification Question Formulation'],
  },
  {
    id: 'agent-coder',
    label: 'Coder Agent',
    role: 'Code Generation & Refinement',
    description: 'Generates clean, production-grade Terraform HCL or Python scripts following retrieved RAG policy rules and reviewer feedback.',
    icon: Braces,
    accent: 'text-cyan-300',
    status: 'Online',
    model: 'GPT-4o',
    systemPrompt: `You are the Senior Coder Agent specializing in Terraform (Azure/AWS) and Python cloud automation.
Write modular, documented, and secure infrastructure code.
Always implement strict security defaults: enforce TLS 1.2+, disable public network access by default, and attach mandatory governance tags.
Respond only with valid, compilable code without conversational fluff.`,
    capabilities: ['Terraform IaC', 'Python Cloud SDKs', 'Reviewer Feedback Adaptation'],
  },
  {
    id: 'agent-reviewer',
    label: 'Reviewer Agent',
    role: 'Quality Assurance & AST Audit',
    description: 'Performs automated code reviews, checks for policy compliance, security flaws, and syntax regressions before deployment.',
    icon: CheckCircle2,
    accent: 'text-emerald-300',
    status: 'Online',
    model: 'GPT-4o',
    systemPrompt: `You are the Principal Security & Code Reviewer Agent.
Analyze the generated artifact against organizational security policies, SAST scan findings, and best practices.
Issue a strict verdict: 'approve' or 'needs_revision'.
If requesting revisions, provide actionable, concise feedback identifying the exact lines and required remediations.`,
    capabilities: ['Code Quality Assessment', 'Security Finding Correlation', 'Revision Enforcing'],
  },
  {
    id: 'agent-rag',
    label: 'Policy RAG Agent',
    role: 'Semantic Knowledge Retrieval',
    description: 'Queries local ChromaDB vector embeddings to inject corporate compliance policies and cloud guardrails into coder context.',
    icon: Boxes,
    accent: 'text-sky-300',
    status: 'Online',
    model: 'ChromaDB Local',
    systemPrompt: `You are the Policy RAG Retrieval Engine.
Perform dense semantic cosine-similarity searches against the corporate cloud governance corpus.
Return top-k policy rules with confidence scores and source document hashes to enforce zero-trust coding standards.`,
    capabilities: ['Vector Similarity Search', 'Cosine Re-ranking', 'Context Boundary Injection'],
  },
  {
    id: 'worker-sandbox',
    label: 'Sandbox Worker',
    role: 'Isolated Execution & Validation',
    description: 'Locked-down Docker container with read-only rootfs validating Python compilation and Terraform formatting in isolation.',
    icon: Lock,
    accent: 'text-amber-300',
    status: 'Healthy',
    model: 'Terraform 1.9.8 + Python 3.12',
    systemPrompt: `Execution sandbox worker running in an isolated network namespace.
Exposes only /validate-python and /validate-terraform endpoints with non-root privileges and strict memory/CPU limits.`,
    capabilities: ['Python Syntax Validation', 'Terraform fmt & validate', 'Zero-Network Execution'],
  },
];

export default function AgentsPage() {
  const [selectedAgent, setSelectedAgent] = useState<AgentCardData | null>(null);

  return (
    <div className="relative min-h-screen overflow-x-hidden text-foreground pb-20">
      <div className="pointer-events-none fixed left-[-10rem] top-32 h-80 w-80 rounded-full bg-cyan-500/[0.05] blur-[100px]" />
      <div className="pointer-events-none fixed right-[-8rem] top-52 h-96 w-96 rounded-full bg-violet-500/[0.06] blur-[120px]" />

      <Header providerMode={PROVIDER_MODE} />
      <AppNav />

      <main className="relative mx-auto max-w-[1600px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {/* Header section */}
        <section className="glass-panel panel-highlight p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <Bot className="h-4 w-4 text-cyan-300" />
                <span className="eyebrow">Multi-Agent Mesh Topology</span>
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-white">
                Agent Fleet & Diagnostics
              </h1>
              <p className="mt-1 text-xs text-slate-400">
                Inspect agent roles, system prompts, active LLM engines, and orchestration topology.
              </p>
            </div>
            <Link href="/">
              <Button size="sm" className="h-9 bg-cyan-300 text-slate-950 font-semibold hover:bg-cyan-200">
                Test In Command Center
              </Button>
            </Link>
          </div>
        </section>

        {/* Mesh Topology Summary Cards */}
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Active Nodes</p>
              <Activity className="h-4 w-4 text-emerald-400" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-emerald-400">5 / 5</p>
            <p className="mt-1 text-[10px] text-slate-500">All agent daemons responsive</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Orchestration Loop</p>
              <Layers className="h-4 w-4 text-cyan-300" />
            </div>
            <p className="mt-3 font-mono text-base font-semibold text-cyan-200">Sequential + Review</p>
            <p className="mt-1 text-[10px] text-slate-500">Planner → Coder ⇄ Reviewer</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Human Gate</p>
              <Shield className="h-4 w-4 text-violet-300" />
            </div>
            <p className="mt-3 font-mono text-base font-semibold text-violet-200">Enforced</p>
            <p className="mt-1 text-[10px] text-slate-500">Plan freeze before coding</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Provider Mode</p>
              <Zap className="h-4 w-4 text-sky-300" />
            </div>
            <p className="mt-3 font-mono text-base font-semibold text-sky-200 uppercase">{PROVIDER_MODE}</p>
            <p className="mt-1 text-[10px] text-slate-500">Azure OpenAI Live Model</p>
          </div>
        </section>

        {/* Agent Cards Grid */}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {AGENTS.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.id}
                className="glass-card panel-highlight p-5 flex flex-col justify-between space-y-4 hover:-translate-y-0.5 hover:border-cyan-300/30 transition group"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03]">
                        <Icon className={`h-5 w-5 ${agent.accent}`} />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-white">{agent.label}</h3>
                        <p className="text-[10px] text-slate-500 font-mono">{agent.id}</p>
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-400/[0.08] px-2 py-0.5 font-mono text-[8px] uppercase tracking-wider text-emerald-400">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      {agent.status}
                    </span>
                  </div>

                  <p className="text-xs leading-relaxed text-slate-300">{agent.description}</p>

                  <div className="space-y-1.5 pt-2 border-t border-white/[0.05]">
                    <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">
                      Capabilities
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {agent.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className="rounded-md border border-white/[0.06] bg-white/[0.02] px-2 py-0.5 text-[9px] text-slate-400 font-mono"
                        >
                          {cap}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between">
                  <span className="font-mono text-[10px] text-slate-500">Engine: {agent.model}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setSelectedAgent(agent)}
                    className="h-7 text-[11px] text-cyan-300 hover:bg-cyan-300/[0.08] hover:text-cyan-200"
                  >
                    <Eye className="mr-1 h-3 w-3" /> Inspect Prompt
                  </Button>
                </div>
              </div>
            );
          })}
        </section>
      </main>

      {/* Reusable accessible Agent Inspector Modal */}
      {selectedAgent && (
        <AgentInspector
          agentId={selectedAgent.id}
          agentLabel={selectedAgent.label}
          isOpen={Boolean(selectedAgent)}
          onClose={() => setSelectedAgent(null)}
          systemPrompt={selectedAgent.systemPrompt}
          inputs="Sample prompt context received from workflow controller."
          outputs="Structured telemetry payload generated by this agent."
        />
      )}
    </div>
  );
}
