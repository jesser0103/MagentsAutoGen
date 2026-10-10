/**
 * Better Auth Next.js catch-all route handler.
 * Mounts all Better Auth endpoints under /api/auth/*
 *
 * Examples:
 *   POST /api/auth/sign-in/email
 *   POST /api/auth/sign-up/email
 *   POST /api/auth/sign-out
 *   GET  /api/auth/session
 *   GET  /api/auth/get-session
 */
import { auth } from '@/lib/auth';
import { toNextJsHandler } from 'better-auth/next-js';

export const { GET, POST } = toNextJsHandler(auth);
