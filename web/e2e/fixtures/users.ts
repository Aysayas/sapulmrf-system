export type Role = 'admin' | 'operator' | 'staff'

export const ROLE_LABEL: Record<Role, string> = {
  admin: 'Barangay Administrator',
  operator: 'MRF Operator',
  staff: 'Authorized Barangay Staff',
}

/** The test admin from .env. Operator and staff accounts are created by the tests that need them. */
export const admin = {
  username: process.env.E2E_ADMIN_USERNAME ?? '',
  password: process.env.E2E_ADMIN_PASSWORD ?? '',
}

/** A unique placeholder account per run, so reruns never collide on usernames. */
export function newAccount(role: Role) {
  const id = Date.now().toString(36)
  return { name: `Test ${ROLE_LABEL[role].split(' ').pop()} ${id}`, username: `e2e.${role}.${id}`, role, password: 'test-password-1' }
}
