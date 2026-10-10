/**
 * One-shot Better Auth migrate + first-admin seed.
 * Used by the Compose `auth-init` service and `npm run bootstrap-admin`.
 */
import { ensureAuthReady } from '../src/lib/auth-ready';

ensureAuthReady()
  .then(() => {
    console.log('Auth schema and bootstrap admin are ready.');
    process.exit(0);
  })
  .catch((error) => {
    console.error('Auth bootstrap failed:', error);
    process.exit(1);
  });
