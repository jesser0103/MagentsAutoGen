'use client';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { EventStreamState } from '@/hooks/useEventStream';
import { Activity, Bot, Cloud, LogOut, ShieldCheck, User } from 'lucide-react';
import { useSession, signOut } from '@/lib/auth-client';

interface HeaderProps {
  providerMode: string;
  connectionState?: EventStreamState;
}

export function Header({ providerMode, connectionState }: HeaderProps) {
  const { data: session } = useSession();
  const currentUser = session?.user?.name || session?.user?.email || null;
  const userRole = session?.user?.role;
  const isAzure = providerMode === 'azure';

  const isLive = connectionState === 'connected';
  const isPending = connectionState === 'connecting' || connectionState === 'reconnecting';
  const isClosed = connectionState === 'closed';
  const isIdle = connectionState === 'idle';

  const statusLabel = isLive
    ? 'Telemetry online'
    : connectionState === 'reconnecting'
    ? 'Reconnecting…'
    : connectionState === 'connecting'
    ? 'Connecting…'
    : isClosed
    ? 'Stream ended'
    : isIdle
    ? 'Telemetry idle'
    : 'Status unknown';

  const statusDotClass = isLive
    ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
    : isPending
    ? 'bg-amber-400 animate-pulse shadow-[0_0_8px_rgba(251,191,36,0.6)]'
    : 'bg-slate-500';

  const statusIconColor = isLive
    ? 'text-emerald-400'
    : isPending
    ? 'text-amber-300'
    : 'text-slate-500';

  return (
    <>
    <header className="fixed inset-x-0 top-0 z-50 border-b border-white/[0.06] bg-[#050812]/72 backdrop-blur-2xl">
      <div className="mx-auto flex h-[72px] max-w-[1600px] items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="ml-16 flex items-center gap-3.5">
          <div className="relative grid h-10 w-10 place-items-center rounded-xl border border-cyan-300/20 bg-cyan-400/[0.07] shadow-[0_0_30px_rgba(34,211,238,0.1)]">
            <Bot className="h-5 w-5 text-cyan-300" />
            <span
              className={cn(
                'absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-[#070a12] transition-colors',
                statusDotClass
              )}
            />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold tracking-[0.02em] text-white sm:text-base">
                MAGENT
              </h1>
              <span className="rounded border border-white/10 px-1.5 py-0.5 font-mono text-[8px] tracking-widest text-slate-500">
                CONTROL PLANE
              </span>
            </div>
            <p className="mt-0.5 hidden text-[10px] uppercase tracking-[0.18em] text-slate-500 sm:block">
              Autonomous infrastructure operations
            </p>
          </div>
        </div>

        <div className="hidden items-center gap-5 lg:flex">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-slate-500">
            <Activity className={cn('h-3.5 w-3.5', statusIconColor, isPending && 'animate-pulse')} />
            <span className={cn(isLive ? 'text-slate-400' : isPending ? 'text-amber-300/90' : 'text-slate-500')}>
              {statusLabel}
            </span>
          </div>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.15em] text-slate-500">
            <ShieldCheck className="h-3.5 w-3.5 text-cyan-300" /> Guardrails active
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="hidden sm:flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-[10px] text-slate-300">
            <User className="h-3 w-3 text-cyan-300" />
            <span className="font-mono text-slate-300">{currentUser || (isAzure ? 'Entra ID SSO' : 'local-operator')}</span>
            {userRole && <span className="text-slate-500">/ {userRole}</span>}
          </div>
          {currentUser && (
            <button
              onClick={() => signOut({ fetchOptions: { onSuccess: () => { window.location.href = '/login'; } } })}
              title="Sign out"
              className="hidden sm:flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-[10px] text-slate-400 hover:border-red-400/20 hover:text-red-300 transition-all"
            >
              <LogOut className="h-3 w-3" />
              <span className="font-mono">Sign out</span>
            </button>
          )}
          <Badge
            variant={isAzure ? 'default' : 'secondary'}
            className="gap-1.5 border-white/10 bg-white/[0.05] px-3 py-1.5 text-[10px] uppercase tracking-wider text-slate-200"
          >
            {isAzure ? <Cloud className="h-3 w-3 text-cyan-300" /> : <Activity className="h-3 w-3 text-violet-300" />}
            {isAzure ? 'Azure live' : 'Demo mesh'}
          </Badge>
        </div>
      </div>
    </header>
    <div aria-hidden="true" className="h-[72px]" />
    </>
  );
}
