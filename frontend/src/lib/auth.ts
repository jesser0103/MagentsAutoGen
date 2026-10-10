/**
 * Better Auth server-side configuration.
 *
 * Uses Postgres via the `pg` driver. Set DATABASE_URL (docker-compose wires
 * it to the postgres service); falls back to localhost for bare-metal dev.
 *
 * JWT plugin enabled so FastAPI backend can verify session tokens
 * using the shared BETTER_AUTH_SECRET without a DB round-trip.
 */
import { betterAuth } from 'better-auth';
import { admin, jwt } from 'better-auth/plugins';
import { Pool } from 'pg';
import { accessControl, roles } from '@/lib/auth-access';

function authDatabaseUrl(): string {
  if (process.env.DATABASE_URL) return process.env.DATABASE_URL;
  const password = encodeURIComponent(process.env.POSTGRES_PASSWORD || 'magent');
  const host = process.env.POSTGRES_HOST || 'localhost';
  const port = process.env.POSTGRES_PORT || '5432';
  const database = process.env.POSTGRES_DB || 'magent_auth';
  const user = process.env.POSTGRES_USER || 'magent';
  return `postgres://${user}:${password}@${host}:${port}/${database}`;
}

const authBaseURL = process.env.BETTER_AUTH_URL || process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

export const auth = betterAuth({
  // -----------------------------------------------------------------------
  // Database — Postgres (docker-compose service `postgres`)
  // -----------------------------------------------------------------------
  database: new Pool({
    connectionString: authDatabaseUrl(),
  }),

  // -----------------------------------------------------------------------
  // Base URL — used for redirects and cookie domains
  // -----------------------------------------------------------------------
  baseURL: authBaseURL,
  secret: process.env.BETTER_AUTH_SECRET || 'dev-secret-change-in-production',
  trustedOrigins: [authBaseURL],

  // -----------------------------------------------------------------------
  // Auth methods
  // -----------------------------------------------------------------------
  emailAndPassword: {
    enabled: true,
    minPasswordLength: 8,
  },

  // Social providers — activate by setting env vars
  socialProviders: {
    ...(process.env.GITHUB_CLIENT_ID
      ? {
          github: {
            clientId: process.env.GITHUB_CLIENT_ID,
            clientSecret: process.env.GITHUB_CLIENT_SECRET || '',
          },
        }
      : {}),
    ...(process.env.MICROSOFT_CLIENT_ID
      ? {
          microsoft: {
            clientId: process.env.MICROSOFT_CLIENT_ID,
            clientSecret: process.env.MICROSOFT_CLIENT_SECRET || '',
            tenantId: process.env.MICROSOFT_TENANT_ID || 'common',
          },
        }
      : {}),
  },

  // -----------------------------------------------------------------------
  // Plugins
  // -----------------------------------------------------------------------
  plugins: [
    // Roles are server-controlled. New users are operators, while an
    // administrator can designate a separate approver through Better Auth.
    admin({
      ac: accessControl,
      roles,
      defaultRole: 'operator',
      adminRoles: ['administrator'],
    }),
    // JWT plugin: issues signed JWTs that FastAPI can verify with PyJWT
    jwt({
      jwt: {
        expirationTime: '8h',
      },
      schema: {
        jwks: {
          modelName: 'jwks',
        },
      },
    }),
  ],

  // -----------------------------------------------------------------------
  // Session configuration
  // -----------------------------------------------------------------------
  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 days
    updateAge: 60 * 60 * 24,      // refresh if older than 1 day
    cookieCache: {
      enabled: true,
      maxAge: 60 * 5, // 5 minutes client-side cache
    },
  },

});

export type Session = typeof auth.$Infer.Session;
export type User = typeof auth.$Infer.Session.user;
