'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AppNav } from '@/components/AppNav';
import { Header } from '@/components/Header';
import { RequestForm } from '@/components/RequestForm';
import { submitRun } from '@/lib/api';
import { saveRunToHistory } from '@/lib/runHistory';
import {
  Activity,
  ArrowRight,
  Bot,
  Boxes,
  Braces,
  CheckCircle2,
  Fingerprint,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

const PROVIDER_MODE = process.env.NEXT_PUBLIC_PROVIDER_MODE || 'demo';

const CAPABILITIES = [
  { icon: Braces, label: 'Code generation', value: 'Python + Terraform', color: 'text-cyan-300' },
  { icon: ShieldCheck, label: 'Security gates', value: 'Policy + SAST + Sandbox', color: 'text-emerald-300' },
  { icon: Fingerprint, label: 'Human control', value: 'Approval enforced', color: 'text-violet-300' },
];

export default function NewMissionPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (userRequest: string) => {
    setLoading(true);
    setError(null);
    try {
      const run = await submitRun(userRequest);
      try {
        localStorage.removeItem('magents_request_draft');
      } catch {
        // Ignore localStorage errors.
      }
      saveRunToHistory(run);
      router.push(`/runs/${encodeURIComponent(run.run_id)}`);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Could not create the workflow run.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-x-hidden pb-20 text-foreground">
      <div className="pointer-events-none fixed left-[-10rem] top-32 h-80 w-80 rounded-full bg-cyan-500/[0.05] blur-[100px]" />
      <div className="pointer-events-none fixed right-[-8rem] top-52 h-96 w-96 rounded-full bg-violet-500/[0.06] blur-[120px]" />

      <Header providerMode={PROVIDER_MODE} />
      <AppNav />

      <main className="relative mx-auto max-w-[1600px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="grid min-h-[520px] items-center gap-10 py-6 lg:grid-cols-[1.08fr_0.92fr]">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-3 py-1.5">
              <span className="status-dot" />
              <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-cyan-100/80">
                Agent mesh ready
              </span>
            </div>
            <h1 className="max-w-3xl text-balance text-3xl font-semibold leading-[1.1] tracking-[-0.04em] text-white sm:text-4xl xl:text-5xl">
              Cloud engineering at the speed of <span className="gradient-text">thought.</span>
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
              Describe the outcome you need. The governed agent mesh will plan, request approval,
              generate, scan, review, and validate the result.
            </p>
            <div className="mt-6 max-w-3xl">
              <RequestForm onSubmit={handleSubmit} loading={loading} error={error} />
            </div>
          </div>

          <div className="relative mx-auto hidden h-[420px] w-full max-w-[480px] place-items-center lg:grid">
            <div className="absolute inset-10 rounded-full border border-cyan-300/[0.08]" />
            <div className="absolute inset-20 animate-orbit rounded-full border border-dashed border-violet-400/15" />
            <div className="absolute inset-28 rounded-full border border-cyan-300/[0.12] bg-cyan-300/[0.015] shadow-[inset_0_0_80px_rgba(34,211,238,0.04)]" />
            <div className="absolute inset-[38%] animate-pulse-glow rounded-3xl border border-cyan-300/30 bg-[#091322] shadow-[0_0_60px_rgba(34,211,238,0.15)]">
              <div className="grid h-full place-items-center"><Bot className="h-10 w-10 text-cyan-200" /></div>
            </div>
            {[
              ['Planner', 'left-[4%] top-[22%]', Sparkles, 'text-violet-300'],
              ['Coder', 'right-[3%] top-[20%]', Braces, 'text-cyan-300'],
              ['Reviewer', 'bottom-[16%] right-[6%]', CheckCircle2, 'text-emerald-300'],
              ['Policy RAG', 'bottom-[14%] left-[5%]', Boxes, 'text-sky-300'],
            ].map(([label, position, Icon, color]) => {
              const NodeIcon = Icon as typeof Bot;
              return (
                <div key={label as string} className={`absolute ${position} animate-float-slow`}>
                  <div className="glass-card flex items-center gap-3 px-3.5 py-2.5">
                    <div className="grid h-7 w-7 place-items-center rounded-lg bg-white/[0.04]">
                      <NodeIcon className={`h-3.5 w-3.5 ${color}`} />
                    </div>
                    <div>
                      <p className="text-[10px] font-medium text-slate-200">{label as string}</p>
                      <p className="mt-0.5 font-mono text-[8px] uppercase tracking-wider text-emerald-400">Online</p>
                    </div>
                  </div>
                </div>
              );
            })}
            <div className="absolute inset-x-20 bottom-0 flex items-center justify-center gap-2 font-mono text-[9px] uppercase tracking-[0.2em] text-slate-600">
              <Activity className="h-3 w-3 text-cyan-400" /> Live orchestration fabric
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {CAPABILITIES.map(({ icon: Icon, label, value, color }, index) => (
            <div key={label} className="glass-card group panel-highlight p-5 transition duration-300 hover:-translate-y-1 hover:border-white/[0.12]">
              <div className="flex items-start justify-between">
                <div className="grid h-9 w-9 place-items-center rounded-xl border border-white/[0.07] bg-white/[0.035]">
                  <Icon className={`h-4 w-4 ${color}`} />
                </div>
                <span className="font-mono text-[9px] text-slate-700">0{index + 1}</span>
              </div>
              <p className="mt-6 data-label">{label}</p>
              <div className="mt-1 flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-200">{value}</p>
                <ArrowRight className="h-3.5 w-3.5 text-slate-700" />
              </div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
