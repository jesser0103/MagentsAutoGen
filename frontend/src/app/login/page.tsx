'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { signIn, useSession } from '@/lib/auth-client';
import { Bot, Github, Loader2, Lock, Mail, ShieldCheck } from 'lucide-react';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get('callbackUrl') || '/';
  const { data: session, isPending } = useSession();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect already-authenticated users
  useEffect(() => {
    if (!isPending && session) {
      router.replace(callbackUrl);
    }
  }, [session, isPending, router, callbackUrl]);

  const handleEmailSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) return;

    setLoading(true);
    setError(null);

    await signIn.email(
      { email: email.trim(), password, callbackURL: callbackUrl },
      {
        onSuccess: () => router.replace(callbackUrl),
        onError: (ctx) => {
          setError(ctx.error.message || 'Invalid email or password.');
          setLoading(false);
        },
      }
    );
  };

  const handleGitHub = async () => {
    setLoading(true);
    await signIn.social({ provider: 'github', callbackURL: callbackUrl });
  };

  const handleMicrosoft = async () => {
    setLoading(true);
    await signIn.social({ provider: 'microsoft', callbackURL: callbackUrl });
  };

  if (isPending || session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#050812]">
        <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#050812] px-4">
      {/* Background glows */}
      <div className="pointer-events-none fixed left-[-10rem] top-24 h-96 w-96 rounded-full bg-cyan-500/[0.07] blur-[100px]" />
      <div className="pointer-events-none fixed right-[-8rem] top-40 h-80 w-80 rounded-full bg-violet-500/[0.08] blur-[120px]" />

      <div className="w-full max-w-sm animate-fade-in">
        {/* Logo / brand */}
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="grid h-14 w-14 place-items-center rounded-2xl border border-cyan-300/20 bg-cyan-400/[0.07] shadow-[0_0_40px_rgba(34,211,238,0.12)]">
            <Bot className="h-7 w-7 text-cyan-300" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              MAGENT <span className="text-cyan-300">Control Plane</span>
            </h1>
            <p className="mt-1 text-xs text-slate-500">Approval-gated autonomous infrastructure</p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6 shadow-[0_0_60px_rgba(0,0,0,0.5)] backdrop-blur-xl">
          <div className="mb-5 flex items-center gap-2">
            <Lock className="h-4 w-4 text-cyan-300" />
            <h2 className="text-sm font-semibold text-white">Sign in to your account</h2>
          </div>

          {/* Error banner */}
          {error && (
            <div className="mb-4 rounded-xl border border-red-400/20 bg-red-950/30 px-3 py-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          {/* Email / password form */}
          <form onSubmit={handleEmailSignIn} className="space-y-3">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@example.com"
                  className="w-full rounded-xl border border-white/[0.08] bg-black/20 py-2.5 pl-9 pr-3 text-sm text-white placeholder:text-slate-700 focus:border-cyan-400/40 focus:outline-none focus:ring-1 focus:ring-cyan-400/20 transition-all"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-white/[0.08] bg-black/20 py-2.5 pl-9 pr-3 text-sm text-white placeholder:text-slate-700 focus:border-cyan-400/40 focus:outline-none focus:ring-1 focus:ring-cyan-400/20 transition-all"
                />
              </div>
            </div>

            <button
              id="btn-sign-in"
              type="submit"
              disabled={loading || !email || !password}
              className="mt-1 flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-400 py-2.5 text-sm font-semibold text-cyan-950 transition-all hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              Sign in
            </button>
          </form>

          {/* Divider */}
          <div className="my-4 flex items-center gap-3">
            <div className="h-px flex-1 bg-white/[0.06]" />
            <span className="text-[10px] uppercase tracking-widest text-slate-600">or</span>
            <div className="h-px flex-1 bg-white/[0.06]" />
          </div>

          {/* Social login */}
          <div className="space-y-2">
            <button
              id="btn-github"
              type="button"
              onClick={handleGitHub}
              disabled={loading}
              className="flex w-full items-center justify-center gap-2.5 rounded-xl border border-white/[0.08] bg-white/[0.03] py-2.5 text-xs font-medium text-slate-300 transition-all hover:border-white/[0.14] hover:bg-white/[0.06] disabled:opacity-50"
            >
              <Github className="h-4 w-4" />
              Continue with GitHub
            </button>
            <button
              id="btn-microsoft"
              type="button"
              onClick={handleMicrosoft}
              disabled={loading}
              className="flex w-full items-center justify-center gap-2.5 rounded-xl border border-white/[0.08] bg-white/[0.03] py-2.5 text-xs font-medium text-slate-300 transition-all hover:border-white/[0.14] hover:bg-white/[0.06] disabled:opacity-50"
            >
              <svg className="h-4 w-4" viewBox="0 0 21 21" fill="none">
                <rect width="10" height="10" fill="#F25022" />
                <rect x="11" width="10" height="10" fill="#7FBA00" />
                <rect y="11" width="10" height="10" fill="#00A4EF" />
                <rect x="11" y="11" width="10" height="10" fill="#FFB900" />
              </svg>
              Continue with Microsoft
            </button>
          </div>

          {/* Register link */}
          <p className="mt-5 text-center text-[11px] text-slate-600">
            No account?{' '}
            <Link href="/register" className="text-cyan-400 hover:text-cyan-300 transition-colors">
              Create one
            </Link>
          </p>
        </div>

        {/* Security note */}
        <p className="mt-4 text-center text-[10px] text-slate-700">
          🔒 All sessions are encrypted. Approval actions are audit-logged.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#050812]">
          <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
