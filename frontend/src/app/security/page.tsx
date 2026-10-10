'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { AppNav } from '@/components/AppNav';
import { Button } from '@/components/ui/button';
import { StatusBadge } from '@/components/StatusBadge';
import { listRuns } from '@/lib/api';
import type { WorkflowRun, SecurityFinding } from '@/lib/types';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Database,
  FileCode,
  Lock,
  RotateCcw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';

const PROVIDER_MODE = process.env.NEXT_PUBLIC_PROVIDER_MODE || 'demo';

const SAMPLE_POLICY_RULES = [
  {
    id: 'SEC-AZ-001',
    category: 'Azure Storage',
    title: 'Require TLS 1.2+ and HTTPS Traffic Only',
    description: 'Storage accounts must deny unencrypted HTTP traffic and enforce minimum TLS version 1.2 across all endpoints.',
    status: 'Enforced',
    source: 'data/internal_rules.txt',
  },
  {
    id: 'SEC-AZ-002',
    category: 'Network Isolation',
    title: 'Deny Public Network Access by Default',
    description: 'Storage accounts and compute resources must disable default public network access and use private endpoints.',
    status: 'Enforced',
    source: 'data/internal_rules.txt',
  },
  {
    id: 'SEC-PY-001',
    category: 'Python Safety',
    title: 'Disallow Unbounded In-Memory Executions & Raw SQL',
    description: 'Generated Python scripts must use parameterized queries, typed models, and structured error handling without eval().',
    status: 'Enforced',
    source: 'config/policies.json',
  },
  {
    id: 'SEC-GOV-001',
    category: 'Governance & FinOps',
    title: 'Mandatory Tagging for Environment and CostCenter',
    description: 'All cloud resources must declare Environment, CostCenter, and ManagedBy tags for FinOps accountability.',
    status: 'Enforced',
    source: 'data/internal_rules.txt',
  },
];

const SCAN_TOOLS = [
  {
    name: 'tfsec',
    focus: 'Terraform & IaC Security',
    description: 'Static analysis for cloud configuration vulnerabilities, open ports, and unencrypted disks.',
    status: 'Active',
    version: '1.28.14',
  },
  {
    name: 'Semgrep & Bandit',
    focus: 'Python SAST & AST Scan',
    description: 'AST analysis checking for injection flaws, dangerous functions, hardcoded secrets, and unsafe imports.',
    status: 'Active',
    version: 'Engine v2',
  },
  {
    name: 'Docker Sandbox',
    focus: 'Runtime Compilation & Terraform Validation',
    description: 'Locked-down, isolated container with read-only rootfs, no socket access, and restricted CPU/Memory.',
    status: 'Active',
    version: 'Hardened Worker',
  },
  {
    name: 'Input Shield',
    focus: 'Prompt Injection & Content Safety',
    description: 'Pre-flight screening evaluating user intents before planner agent ingestion.',
    status: 'Active',
    version: 'Shield v1',
  },
];

export default function SecurityPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await listRuns(50);
      setRuns(data);
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  // Collect all findings across all loaded runs
  const allFindings: Array<SecurityFinding & { run_id: string }> = runs.flatMap((r) =>
    (r.scans || []).flatMap((s) => (s.findings || []).map((f) => ({ ...f, run_id: r.run_id })))
  );

  const criticalCount = allFindings.filter((f) => f.severity.toLowerCase() === 'critical').length;
  const highCount = allFindings.filter((f) => f.severity.toLowerCase() === 'high').length;
  const totalScans = runs.reduce((sum, r) => sum + (r.scans?.length || 0), 0);

  const filteredRules = SAMPLE_POLICY_RULES.filter(
    (rule) =>
      rule.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const pendingApprovalsCount = runs.filter(
    (r) => r.status === 'awaiting_approval' || r.status === 'needs_clarification'
  ).length;

  return (
    <div className="relative min-h-screen overflow-x-hidden text-foreground pb-20">
      <div className="pointer-events-none fixed left-[-10rem] top-32 h-80 w-80 rounded-full bg-cyan-500/[0.05] blur-[100px]" />
      <div className="pointer-events-none fixed right-[-8rem] top-52 h-96 w-96 rounded-full bg-violet-500/[0.06] blur-[120px]" />

      <Header providerMode={PROVIDER_MODE} />
      <AppNav pendingApprovalsCount={pendingApprovalsCount} />

      <main className="relative mx-auto max-w-[1600px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {/* Header section */}
        <section className="glass-panel panel-highlight p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <ShieldCheck className="h-4 w-4 text-cyan-300" />
                <span className="eyebrow">Security & Governance Mesh</span>
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-white">
                Policy Guardrails & Security Scanner
              </h1>
              <p className="mt-1 text-xs text-slate-400">
                Automated multi-layer security posture combining RAG policy retrieval, SAST, and sandbox validation.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void loadData()}
              disabled={loading}
              className="h-9 border-white/10 bg-white/[0.03]"
            >
              <RotateCcw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Scans
            </Button>
          </div>
        </section>

        {/* Security Posture KPI Cards */}
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Total Scans Run</p>
              <Shield className="h-4 w-4 text-cyan-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-white">{totalScans}</p>
            <p className="mt-1 text-[10px] text-slate-500">Across active missions</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Critical Findings</p>
              <ShieldAlert className="h-4 w-4 text-red-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-red-300">{criticalCount}</p>
            <p className="mt-1 text-[10px] text-slate-500">
              {highCount} high severity detected
            </p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">RAG Vector Rules</p>
              <Database className="h-4 w-4 text-emerald-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-emerald-300">
              {SAMPLE_POLICY_RULES.length}
            </p>
            <p className="mt-1 text-[10px] text-slate-500">ChromaDB semantic memory</p>
          </div>

          <div className="glass-card panel-highlight p-4">
            <div className="flex items-center justify-between">
              <p className="data-label">Sandbox Posture</p>
              <Lock className="h-4 w-4 text-violet-300" />
            </div>
            <p className="mt-3 font-mono text-2xl font-semibold text-violet-200">100%</p>
            <p className="mt-1 text-[10px] text-slate-500">Read-only rootfs isolated</p>
          </div>
        </section>

        {/* Scanner Engine Architecture Grid */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-cyan-300" />
            <h2 className="text-sm font-semibold text-white">Active Defense Layers</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {SCAN_TOOLS.map((tool) => (
              <div key={tool.name} className="glass-card panel-highlight p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-cyan-300">{tool.name}</span>
                  <span className="rounded-full border border-emerald-400/20 bg-emerald-400/[0.08] px-2 py-0.5 font-mono text-[8px] uppercase tracking-wider text-emerald-400">
                    {tool.status}
                  </span>
                </div>
                <p className="text-[11px] font-medium text-slate-200">{tool.focus}</p>
                <p className="text-[10px] leading-relaxed text-slate-400">{tool.description}</p>
                <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between font-mono text-[9px] text-slate-500">
                  <span>Engine</span>
                  <span>{tool.version}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* RAG Policy Knowledge Base Explorer */}
        <section className="glass-card p-5 space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-white/[0.06] pb-3">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-purple-300" />
              <h3 className="text-sm font-semibold text-white">RAG Policy Knowledge Base (ChromaDB)</h3>
            </div>
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search policy rule…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-white/[0.08] bg-black/20 pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:border-cyan-300/40 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {filteredRules.map((rule) => (
              <div
                key={rule.id}
                className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4 space-y-2 hover:border-purple-300/30 transition"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-purple-300">{rule.id}</span>
                  <span className="rounded border border-white/10 px-1.5 py-0.5 text-[9px] font-mono text-slate-400">
                    {rule.category}
                  </span>
                </div>
                <h4 className="text-xs font-medium text-slate-200">{rule.title}</h4>
                <p className="text-[11px] leading-5 text-slate-400">{rule.description}</p>
                <div className="flex items-center justify-between pt-2 border-t border-white/[0.05] font-mono text-[9px] text-slate-500">
                  <span>Source: {rule.source}</span>
                  <span className="text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" /> {rule.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
