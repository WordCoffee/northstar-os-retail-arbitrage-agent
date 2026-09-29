// UI role -> backend canonical role map (F5).
//
// The backend role enum is canonical and must not drift:
//   viewer, analyst, operator, organization_admin, organization_owner,
//   internal_platform_admin
//
// The UI shell uses a smaller set of display roles. This module is the single
// place that translates between them so permission checks cannot silently
// diverge from the server contract.

export const BACKEND_ROLES = [
  'viewer',
  'analyst',
  'operator',
  'organization_admin',
  'organization_owner',
  'internal_platform_admin',
]

// One UI display role may map to more than one backend role the principal holds.
export const UI_ROLE_TO_BACKEND = {
  // Not yet a member of any organization.
  invitee: ['viewer'],
  // An organization's own user (owner also holds admin capabilities).
  customer: ['organization_owner', 'organization_admin'],
  customer_admin: ['organization_admin'],
  // Internal operator.
  operator: ['operator', 'analyst'],
  // Internal platform administrator (the owner).
  platform_admin: ['internal_platform_admin'],
}

export function toBackendRoles(uiRole) {
  return UI_ROLE_TO_BACKEND[uiRole] || ['viewer']
}

export function isBackendRole(value) {
  return BACKEND_ROLES.includes(value)
}