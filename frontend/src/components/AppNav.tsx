'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useSession } from '@/lib/auth-client';
import { hasRole } from '@/lib/auth-access';
import {
  Bot,
  CircleDollarSign,
  LayoutDashboard,
  Menu,
  Rocket,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from 'lucide-react';

interface AppNavProps {
  pendingApprovalsCount?: number;
}

const NAV_ITEMS: {
  href: string;
  label: string;
  description: string;
  icon: typeof LayoutDashboard;
  badgeKey: 'pendingApprovals' | null;
  exact: boolean;
  adminOnly?: boolean;
}[] = [
  {
    href: '/',
    label: 'Overview',
    description: 'Control-plane activity and operational summary',
    icon: LayoutDashboard,
    badgeKey: null,
    exact: true,
  },
  {
    href: '/new-mission',
    label: 'New Mission',
    description: 'Write a command and initialize a workflow',
    icon: Sparkles,
    badgeKey: null,
    exact: true,
  },
  {
    href: '/runs',
    label: 'Missions',
    description: 'Workflow runs, approvals, and history',
    icon: Rocket,
    badgeKey: 'pendingApprovals',
    exact: false,
  },
  {
    href: '/finops',
    label: 'FinOps',
    description: 'Token usage and estimated costs',
    icon: CircleDollarSign,
    badgeKey: null,
    exact: false,
  },
  {
    href: '/security',
    label: 'Security & RAG',
    description: 'Findings, policies, and retrieval evidence',
    icon: ShieldCheck,
    badgeKey: null,
    exact: false,
  },
  {
    href: '/agents',
    label: 'Agent Fleet',
    description: 'Agent roles, capabilities, and diagnostics',
    icon: Bot,
    badgeKey: null,
    exact: false,
  },
  {
    href: '/admin/users',
    label: 'Users',
    description: 'Roles, accounts, and access',
    icon: Users,
    badgeKey: null,
    exact: false,
    adminOnly: true,
  },
];

export function AppNav({ pendingApprovalsCount = 0 }: AppNavProps) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const isAdmin = hasRole(session?.user?.role, 'administrator');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return undefined;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open]);

  const isItemActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);

  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Close dashboard navigation"
          className="fixed inset-0 z-30 cursor-default bg-black/20 backdrop-blur-[1px]"
          onClick={() => setOpen(false)}
        />
      )}

      <div className="fixed left-2 top-2 z-[60]">
        <button
          type="button"
          aria-label={open ? 'Close dashboard navigation' : 'Open dashboard navigation'}
          aria-expanded={open}
          aria-controls="dashboard-navigation-panel"
          onClick={() => setOpen((current) => !current)}
          className={cn(
            'grid h-14 w-14 place-items-center rounded-xl border bg-[#08111f]/95 shadow-[0_0_30px_rgba(34,211,238,0.1)] backdrop-blur-2xl transition-all duration-200',
            open
              ? 'border-cyan-300/30 bg-cyan-300/[0.08] text-cyan-300'
              : 'border-white/[0.09] text-slate-400 hover:border-cyan-300/25 hover:bg-cyan-300/[0.05] hover:text-cyan-200'
          )}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>

        <nav
          id="dashboard-navigation-panel"
          aria-label="Dashboard navigation"
          className={cn(
            'glass-panel absolute left-0 top-16 w-[290px] origin-top-left overflow-hidden p-2 transition-all duration-200',
            open
              ? 'pointer-events-auto translate-y-0 scale-100 opacity-100'
              : 'pointer-events-none -translate-y-2 scale-95 opacity-0'
          )}
        >
          <div className="border-b border-white/[0.06] px-3 py-2.5">
            <p className="eyebrow">Control plane</p>
            <p className="mt-1 text-[10px] text-slate-500">Choose a dashboard area</p>
          </div>

          <div className="mt-1.5 space-y-1">
            {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => {
              const Icon = item.icon;
              const active = isItemActive(item.href, item.exact);
              const showBadge =
                item.badgeKey === 'pendingApprovals' && pendingApprovalsCount > 0;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? 'page' : undefined}
                  onClick={() => setOpen(false)}
                  className={cn(
                    'group flex items-center gap-3 rounded-xl border px-3 py-3 transition-all duration-200',
                    active
                      ? 'border-cyan-300/30 bg-cyan-300/[0.08] text-white shadow-[0_0_24px_rgba(34,211,238,0.1)]'
                      : 'border-transparent text-slate-400 hover:border-white/[0.07] hover:bg-white/[0.03] hover:text-slate-200'
                  )}
                >
                  <div
                    className={cn(
                      'grid h-9 w-9 shrink-0 place-items-center rounded-lg border transition-colors',
                      active
                        ? 'border-cyan-300/20 bg-cyan-300/[0.07]'
                        : 'border-white/[0.07] bg-white/[0.025]'
                    )}
                  >
                    <Icon className={cn('h-4 w-4', active ? 'text-cyan-300' : 'text-slate-500')} />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium">{item.label}</span>
                      {showBadge && (
                        <span className="inline-flex min-w-4 items-center justify-center rounded-full border border-amber-300/40 bg-amber-400/20 px-1.5 py-0.5 font-mono text-[8px] font-semibold text-amber-200">
                          {pendingApprovalsCount}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-[9px] text-slate-600 group-hover:text-slate-500">
                      {item.description}
                    </p>
                  </div>
                </Link>
              );
            })}
          </div>
        </nav>
      </div>
    </>
  );
}
