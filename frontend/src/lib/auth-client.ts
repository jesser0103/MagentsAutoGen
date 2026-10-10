'use client';

/**
 * Better Auth React client.
 *
 * Provides hooks and functions for use in Client Components:
 *   useSession()  — reactive session state
 *   signIn        — email/password and social login methods
 *   signUp        — email/password registration
 *   signOut       — clear session and redirect
 *   getSession    — imperative one-shot session fetch (for api.ts)
 */
import { createAuthClient } from 'better-auth/react';
import { adminClient, jwtClient } from 'better-auth/client/plugins';
import { accessControl, roles } from '@/lib/auth-access';

export const authClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
  plugins: [
    // Mirrors the server admin plugin so session users expose their role.
    adminClient({ ac: accessControl, roles }),
    // Provides the JWT plugin's JWKS client actions. API calls obtain a session
    // token from Better Auth's built-in /api/auth/token endpoint.
    jwtClient(),
  ],
});

export const signIn = authClient.signIn;
export const signUp = authClient.signUp;
export const signOut = authClient.signOut;
export const useSession = authClient.useSession;
export const getSession = authClient.getSession;
