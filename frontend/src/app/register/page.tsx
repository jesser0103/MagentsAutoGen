'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { signUp, useSession } from '@/lib/auth-client';
import { Bot, Loader2, Lock, Mail, ShieldCheck, User } from 'lucide-react';

export default function RegisterPage() {
  const router = useRouter();
  const { data: session, isPending } = useSession();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect already-authenticated users
  useEffect(() => {
    if (!isPending && session) router.replace('/');
  }, [session, isPending, router]);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setLoading(true);
    setError(null);

    await signUp.email(
      { name: name.trim(), email: email.trim(), password, callbackURL: '/' },
      {
        onSuccess: () => router.replace('/'),
        onError: (ctx) => {
          setError(ctx.error.message || 'Could not create account.');
          setLoading(false);
        },
      }
    );
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
        {/* Brand */}
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="grid h-14 w-14 place-items-center rounded-2xl border border-cyan-300/20 bg-cyan-400/[0.07] shadow-[0_0_40px_rgba(34,211,238,0.12)]">
            <Bot className="h-7 w-7 text-cyan-300" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              MAGENT <span className="text-cyan-300">Control Plane</span>
            </h1>
            <p className="mt-1 text-xs text-slate-500">Create your operator account</p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6 shadow-[0_0_60px_rgba(0,0,0,0.5)] backdrop-blur-xl">
          <div className="mb-5 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-white">New operator account</h2>
          </div>

          {error && (
            <div className="mb-4 rounded-xl border border-red-400/20 bg-red-950/30 px-3 py-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-3">
            {/* Name */}
            <div>
              <label htmlFor="name" className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">
                Full name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
                <input
                  id="name"
                  type="text"
                  autoComplete="name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Smith"
                  className="w-full rounded-xl border border-white/[0.08] bg-black/20 py-2.5 pl-9 pr-3 text-sm text-white placeholder:text-slate-700 focus:border-cyan-400/40 focus:outline-none focus:ring-1 focus:ring-cyan-400/20 transition-all"
                />
              </div>
            </div>

            {/* Email */}
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

            {/* Password */}
            <div>
              <label htmlFor="password" className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  className="w-full rounded-xl border border-white/[0.08] bg-black/20 py-2.5 pl-9 pr-3 text-sm text-white placeholder:text-slate-700 focus:border-cyan-400/40 focus:outline-none focus:ring-1 focus:ring-cyan-400/20 transition-all"
                />
              </div>
            </div>

            {/* Confirm */}
            <div>
              <label htmlFor="confirm" className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">
                Confirm password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
                <input
                  id="confirm"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Repeat password"
                  className={`w-full rounded-xl border bg-black/20 py-2.5 pl-9 pr-3 text-sm text-white placeholder:text-slate-700 focus:outline-none focus:ring-1 transition-all ${
                    confirm && confirm !== password
                      ? 'border-red-400/40 focus:border-red-400/60 focus:ring-red-400/20'
                      : 'border-white/[0.08] focus:border-cyan-400/40 focus:ring-cyan-400/20'
                  }`}
                />
              </div>
            </div>

            <button
              id="btn-register"
              type="submit"
              disabled={loading || !name || !email || !password || !confirm}
              className="mt-1 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-400 py-2.5 text-sm font-semibold text-emerald-950 transition-all hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              Create account
            </button>
          </form>

          <p className="mt-5 text-center text-[11px] text-slate-600">
            Already have an account?{' '}
            <Link href="/login" className="text-cyan-400 hover:text-cyan-300 transition-colors">
              Sign in
            </Link>
          </p>
        </div>

        <p className="mt-4 text-center text-[10px] text-slate-700">
          🔒 Account credentials are stored locally and never shared.
        </p>
      </div>
    </div>
  );
}
