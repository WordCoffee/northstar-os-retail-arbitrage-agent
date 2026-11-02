// Service entitlement gate — one function, one file.
//
// In development every service is open: the studio is local and free. In
// production this is where a real gate lives:
//
//   * a service runs only while the account has studio credit,
//   * credit is deducted BEFORE the job is enqueued,
//   * the decision is enforced server-side, not here — this function only keeps
//     the UI honest about what the server will allow.
//
// See docs/UX_SYSTEM.md (U14) and reports/ty/needs_you.md #2 for the processor
// setup, which is owner-only.

import { SERVICE_REGISTRY, getService } from '../data/serviceRegistry.js'

export const GATE_MODES = { dev: 'dev_open', entitled: 'entitled', denied: 'denied', unknown: 'unknown_service' }

/**
 * Can this session use this service?
 *
 * Returns `{ allowed, mode, reason }`. Never throws: an unknown service is a
 * denial with a named reason, not an exception, because the tab bar renders the
 * answer for every registry entry.
 */
export function canUseService(session, serviceId, options = {}) {
  const service = getService(serviceId)
  if (!service) {
    return { allowed: false, mode: GATE_MODES.unknown, reason: `unknown service ${serviceId}` }
  }

  // Dev is open. `enforceBilling` lets a test (or a staging build) exercise the
  // production branch without pretending dev is production.
  const enforce = options.enforceBilling === true || session?.enforceBilling === true
  if (!enforce) {
    return { allowed: true, mode: GATE_MODES.dev, reason: 'studio entitlement is open in dev' }
  }

  const entitlement = session?.entitlements?.[service.entitlementKey]
  if (entitlement === true) {
    return { allowed: true, mode: GATE_MODES.entitled, reason: service.entitlementKey }
  }

  const credit = Number(session?.studioCredit ?? 0)
  if (credit > 0) {
    return { allowed: true, mode: GATE_MODES.entitled, reason: `${credit} studio credit` }
  }

  return { allowed: false, mode: GATE_MODES.denied, reason: 'no studio credit' }
}

/** Every interactive service with its decision — what a tab bar or menu renders. */
export function serviceAccessMap(session, options = {}) {
  const out = {}
  for (const entry of (options.registry || SERVICE_REGISTRY)) {
    out[entry.id] = canUseService(session, entry.id, options)
  }
  return out
}
