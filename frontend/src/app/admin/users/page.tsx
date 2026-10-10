import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth';
import { hasRole } from '@/lib/auth-access';
import { UserManagement } from '@/components/admin/UserManagement';
import { Header } from '@/components/Header';
import { AppNav } from '@/components/AppNav';

export const dynamic = 'force-dynamic';

export const metadata = {
  title: 'Admin · Users — Magent Control Plane',
};

/**
 * Hidden admin page — server-side gate.
 *
 * The session is resolved on every request (force-dynamic); anyone without
 * the `administrator` role is bounced to `/` before a single byte of the
 * management UI ships to the browser. The client component then performs
 * all mutations through the Better Auth Admin API, so access control,
 * permission checks, and audit trails stay enforced server-side.
 */
export default async function AdminUsersPage() {
  const session = await auth.api.getSession({ headers: await headers() });

  if (!session || !hasRole(session.user.role, 'administrator')) {
    redirect('/');
  }

  return (
    <div className="relative min-h-screen overflow-x-hidden pb-20 text-foreground">
      <div className="pointer-events-none fixed left-[-10rem] top-32 h-80 w-80 rounded-full bg-cyan-500/[0.05] blur-[100px]" />
      <div className="pointer-events-none fixed right-[-8rem] top-52 h-96 w-96 rounded-full bg-violet-500/[0.06] blur-[120px]" />
      <Header providerMode={process.env.NEXT_PUBLIC_PROVIDER_MODE || 'demo'} />
      <AppNav />
      <main className="relative mx-auto max-w-[1600px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <UserManagement currentUserId={session.user.id} />
      </main>
    </div>
  );
}
