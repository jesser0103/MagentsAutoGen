'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  Ban,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Shield,
  UserPlus,
  Users,
} from 'lucide-react';
import { authClient } from '@/lib/auth-client';
import { AUTH_ROLES, type AuthRole, parseRoles } from '@/lib/auth-access';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const PAGE_SIZE = 20;

type AdminUser = {
  id: string;
  name: string;
  email: string;
  role?: string | null;
  banned?: boolean | null;
  banReason?: string | null;
  createdAt: string | Date;
};

const ROLE_STYLES: Record<string, string> = {
  administrator: 'border-violet-400/30 bg-violet-400/[0.08] text-violet-200',
  approver: 'border-amber-400/30 bg-amber-400/[0.08] text-amber-200',
  operator: 'border-cyan-400/20 bg-cyan-400/[0.07] text-cyan-200',
};

const inputClass =
  'w-full rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2.5 text-sm text-white placeholder:text-slate-700 focus:border-cyan-400/40 focus:outline-none focus:ring-1 focus:ring-cyan-400/20';

function formatDate(value: string | Date) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function errorMessage(error: unknown, fallback: string) {
  if (error && typeof error === 'object' && 'message' in error) {
    const message = (error as { message?: string }).message;
    if (message) return message;
  }
  return fallback;
}

interface UserManagementProps {
  currentUserId: string;
}

export function UserManagement({ currentUserId }: UserManagementProps) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [mutatingId, setMutatingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<AuthRole>('operator');

  const loadUsers = useCallback(async (nextOffset = 0, nextSearch = appliedSearch) => {
    setLoading(true);
    try {
      const { data, error } = await authClient.admin.listUsers({
        query: {
          limit: PAGE_SIZE,
          offset: nextOffset,
          sortBy: 'createdAt',
          sortDirection: 'desc',
          ...(nextSearch
            ? {
                searchValue: nextSearch,
                searchField: 'email',
                searchOperator: 'contains',
              }
            : {}),
        },
      });

      if (error) {
        toast.error(errorMessage(error, 'Could not load users.'));
        return;
      }

      setUsers((data?.users as AdminUser[]) ?? []);
      setTotal(data?.total ?? 0);
      setOffset(nextOffset);
    } finally {
      setLoading(false);
    }
  }, [appliedSearch]);

  useEffect(() => {
    void loadUsers(0, appliedSearch);
  }, [appliedSearch, loadUsers]);

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  const roleCounts = useMemo(() => {
    const counts = { administrator: 0, approver: 0, operator: 0 };
    for (const user of users) {
      const [primary] = parseRoles(user.role);
      if (primary && primary in counts) {
        counts[primary as AuthRole] += 1;
      }
    }
    return counts;
  }, [users]);

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    setAppliedSearch(search.trim());
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!newName.trim() || !newEmail.trim() || newPassword.length < 8) {
      toast.error('Name, email, and an 8+ character password are required.');
      return;
    }

    setCreating(true);
    const { error } = await authClient.admin.createUser({
      name: newName.trim(),
      email: newEmail.trim(),
      password: newPassword,
      role: newRole,
    });
    setCreating(false);

    if (error) {
      toast.error(errorMessage(error, 'Could not create user.'));
      return;
    }

    toast.success(`Created ${newEmail.trim()} as ${newRole}.`);
    setNewName('');
    setNewEmail('');
    setNewPassword('');
    setNewRole('operator');
    await loadUsers(0, appliedSearch);
  };

  const handleSetRole = async (user: AdminUser, role: AuthRole) => {
    if (user.id === currentUserId) return;
    setMutatingId(user.id);
    const { error } = await authClient.admin.setRole({
      userId: user.id,
      role,
    });
    setMutatingId(null);

    if (error) {
      toast.error(errorMessage(error, 'Could not update role.'));
      return;
    }

    toast.success(`Updated ${user.email} to ${role}.`);
    await loadUsers(offset, appliedSearch);
  };

  const handleToggleBan = async (user: AdminUser) => {
    if (user.id === currentUserId) return;
    setMutatingId(user.id);
    const { error } = user.banned
      ? await authClient.admin.unbanUser({ userId: user.id })
      : await authClient.admin.banUser({
          userId: user.id,
          banReason: 'Suspended by administrator from control plane',
        });
    setMutatingId(null);

    if (error) {
      toast.error(errorMessage(error, user.banned ? 'Could not restore user.' : 'Could not ban user.'));
      return;
    }

    toast.success(user.banned ? `Restored ${user.email}.` : `Banned ${user.email}.`);
    await loadUsers(offset, appliedSearch);
  };

  return (
    <div className="space-y-6">
      <section className="glass-panel panel-highlight p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="mb-1.5 flex items-center gap-2">
              <Users className="h-4 w-4 text-cyan-300" />
              <span className="eyebrow">Access control</span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-white">User management</h1>
            <p className="mt-1 max-w-2xl text-xs text-slate-400">
              Create accounts and assign operator, approver, or administrator roles. Mutations go
              through the Better Auth Admin API and stay server-enforced.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => void loadUsers(offset, appliedSearch)}
            className="h-9 border border-white/[0.08] text-slate-300 hover:bg-white/[0.04]"
          >
            <RefreshCw className={cn('mr-1.5 h-3.5 w-3.5', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {AUTH_ROLES.map((role) => (
          <div key={role} className="glass-card panel-highlight p-4">
            <p className="data-label">{role}</p>
            <p className="mt-3 font-mono text-2xl font-semibold text-white">{roleCounts[role]}</p>
            <p className="mt-1 text-[10px] text-slate-500">On this page</p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <form onSubmit={handleCreate} className="glass-panel panel-highlight h-fit space-y-4 p-5">
          <div className="flex items-center gap-2">
            <UserPlus className="h-4 w-4 text-cyan-300" />
            <h2 className="text-sm font-semibold text-white">Create user</h2>
          </div>

          <label className="block space-y-1.5">
            <span className="text-[10px] uppercase tracking-widest text-slate-500">Name</span>
            <input
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              className={inputClass}
              autoComplete="off"
              required
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-[10px] uppercase tracking-widest text-slate-500">Email</span>
            <input
              type="email"
              value={newEmail}
              onChange={(event) => setNewEmail(event.target.value)}
              className={inputClass}
              autoComplete="off"
              required
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-[10px] uppercase tracking-widest text-slate-500">Password</span>
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className={inputClass}
              minLength={8}
              autoComplete="new-password"
              required
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-[10px] uppercase tracking-widest text-slate-500">Role</span>
            <select
              value={newRole}
              onChange={(event) => setNewRole(event.target.value as AuthRole)}
              className={inputClass}
            >
              {AUTH_ROLES.map((role) => (
                <option key={role} value={role} className="bg-slate-950">
                  {role}
                </option>
              ))}
            </select>
          </label>

          <Button
            type="submit"
            disabled={creating}
            className="h-9 w-full bg-cyan-300 text-slate-950 font-semibold hover:bg-cyan-200"
          >
            {creating ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Plus className="mr-1.5 h-3.5 w-3.5" />}
            Create account
          </Button>
        </form>

        <div className="glass-panel panel-highlight overflow-hidden">
          <form
            onSubmit={handleSearch}
            className="flex flex-col gap-3 border-b border-white/[0.06] p-4 sm:flex-row sm:items-center"
          >
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by email"
                className={cn(inputClass, 'pl-9')}
              />
            </div>
            <Button
              type="submit"
              size="sm"
              className="h-10 bg-cyan-300 text-slate-950 font-semibold hover:bg-cyan-200"
            >
              Search
            </Button>
          </form>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-[10px] uppercase tracking-widest text-slate-500">
                <tr className="border-b border-white/[0.06]">
                  <th className="px-4 py-3 font-medium">User</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading && users.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-16 text-center text-slate-500">
                      <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-cyan-300" />
                      Loading directory…
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-16 text-center text-slate-500">
                      No users match this query.
                    </td>
                  </tr>
                ) : (
                  users.map((user) => {
                    const isSelf = user.id === currentUserId;
                    const currentRole = (parseRoles(user.role)[0] || 'operator') as AuthRole;
                    const busy = mutatingId === user.id;

                    return (
                      <tr key={user.id} className="border-b border-white/[0.04] last:border-0">
                        <td className="px-4 py-3">
                          <p className="font-medium text-white">{user.name || '—'}</p>
                          <p className="font-mono text-[11px] text-slate-500">{user.email}</p>
                        </td>
                        <td className="px-4 py-3">
                          <select
                            value={AUTH_ROLES.includes(currentRole) ? currentRole : 'operator'}
                            disabled={isSelf || busy}
                            onChange={(event) => void handleSetRole(user, event.target.value as AuthRole)}
                            className={cn(
                              'rounded-lg border bg-black/20 px-2 py-1.5 text-xs capitalize',
                              ROLE_STYLES[currentRole] ?? ROLE_STYLES.operator,
                              (isSelf || busy) && 'opacity-60'
                            )}
                          >
                            {AUTH_ROLES.map((role) => (
                              <option key={role} value={role} className="bg-slate-950 text-white">
                                {role}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          {user.banned ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-red-400/30 bg-red-400/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-red-300">
                              <Ban className="h-3 w-3" />
                              Banned
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-emerald-300">
                              Active
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-slate-500">
                          {formatDate(user.createdAt)}
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={isSelf || busy}
                            onClick={() => void handleToggleBan(user)}
                            className={cn(
                              'h-8 text-[11px]',
                              user.banned
                                ? 'text-emerald-300 hover:bg-emerald-400/[0.08]'
                                : 'text-red-300 hover:bg-red-400/[0.08]'
                            )}
                          >
                            {busy ? (
                              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                            ) : (
                              <Shield className="mr-1 h-3 w-3" />
                            )}
                            {isSelf ? 'You' : user.banned ? 'Restore' : 'Ban'}
                          </Button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-3 text-[11px] text-slate-500">
            <span>
              {total === 0 ? '0 users' : `${pageStart}–${pageEnd} of ${total}`}
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={!canPrev || loading}
                onClick={() => void loadUsers(Math.max(0, offset - PAGE_SIZE), appliedSearch)}
                className="h-8 border border-white/[0.08]"
              >
                Previous
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={!canNext || loading}
                onClick={() => void loadUsers(offset + PAGE_SIZE, appliedSearch)}
                className="h-8 border border-white/[0.08]"
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
