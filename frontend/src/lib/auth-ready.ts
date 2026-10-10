/**
 * Apply Better Auth schema migrations and seed the first administrator.
 *
 * Safe to call more than once: migrations are additive, and the bootstrap
 * user is created only when that email is missing.
 */
import { auth } from '@/lib/auth';

let ready: Promise<void> | null = null;

export function ensureAuthReady(): Promise<void> {
  ready ??= prepareAuth();
  return ready;
}

async function prepareAuth(): Promise<void> {
  const ctx = await auth.$context;
  await ctx.runMigrations();
  await seedBootstrapAdmin(ctx);
}

async function seedBootstrapAdmin(
  ctx: Awaited<typeof auth.$context>
): Promise<void> {
  const email = process.env.BOOTSTRAP_ADMIN_EMAIL?.trim().toLowerCase();
  const password = process.env.BOOTSTRAP_ADMIN_PASSWORD;

  if (!email || !password) {
    console.info(
      '[auth] BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD not set; skipping first-admin seed.'
    );
    return;
  }

  if (password.length < 8) {
    console.warn(
      '[auth] BOOTSTRAP_ADMIN_PASSWORD must be at least 8 characters; skipping first-admin seed.'
    );
    return;
  }

  const existing = await ctx.internalAdapter.findUserByEmail(email);
  if (existing?.user) {
    console.info(`[auth] Bootstrap admin ${email} already exists.`);
    return;
  }

  await auth.api.createUser({
    body: {
      email,
      password,
      name: process.env.BOOTSTRAP_ADMIN_NAME?.trim() || 'Administrator',
      role: 'administrator',
    },
  });

  console.info(`[auth] Created bootstrap administrator ${email}.`);
}
