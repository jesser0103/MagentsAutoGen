/**
 * Shared Better Auth access-control statements and roles.
 *
 * Imported by both the server `auth` instance and the React client so
 * permission checks stay aligned. Keep this module free of Node-only
 * imports (no `pg`, no `betterAuth()`).
 */
import { createAccessControl } from 'better-auth/plugins/access';
import { adminAc, defaultStatements } from 'better-auth/plugins/admin/access';

export const AUTH_ROLES = ['operator', 'approver', 'administrator'] as const;
export type AuthRole = (typeof AUTH_ROLES)[number];

export const accessControl = createAccessControl({
  ...defaultStatements,
  mission: ['submit', 'approve', 'reject'],
} as const);

export const roles = {
  operator: accessControl.newRole({
    mission: ['submit'],
    user: [],
    session: [],
  }),
  approver: accessControl.newRole({
    mission: ['submit', 'approve', 'reject'],
    user: [],
    session: [],
  }),
  administrator: accessControl.newRole({
    ...adminAc.statements,
    mission: ['submit', 'approve', 'reject'],
  }),
};

export function parseRoles(roleField?: string | null): string[] {
  return (roleField ?? '')
    .split(',')
    .map((role) => role.trim())
    .filter(Boolean);
}

export function hasRole(roleField: string | null | undefined, role: AuthRole): boolean {
  return parseRoles(roleField).includes(role);
}
