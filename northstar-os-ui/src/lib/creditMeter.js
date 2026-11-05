// Credit meter — display-only arithmetic over the credit ledger.
//
// Contract (credit-ledger/v1 §3, C8): the client only DISPLAYS the balance and
// never computes cost logic. It must not invent one either. Before this module
// the Package Design page carried a hardcoded starting balance and subtracted a
// cost locally on every run, which is a number the ledger has never seen.
//
// So: read GET /api/v1/credits/me, normalise it, and answer exactly one
// question — is this named action affordable? A malformed or missing payload
// becomes an explicit unknown state, never a fabricated figure.

/** Credits one AI Design run is priced at (catalog price, not computed here). */
export const AI_DESIGN_COST = 10

const UNKNOWN = Object.freeze({
  ok: false,
  reason: 'meter_unavailable',
  balance: null,
  allotment: null,
  consumed: null,
  plan: '',
  period: '',
})

/**
 * Normalise the `GET /api/v1/credits/me` payload.
 *
 * Accepts the bff/v1 envelope (`{ data: {...} }`) or the bare data object.
 * Returns `{ ok: true, balance, allotment, consumed, plan, period }` only when
 * `balance` is a finite number; anything else returns the unknown state with a
 * named reason so the UI can say what is missing.
 */
export function normaliseMeter(payload) {
  const body = payload && typeof payload === 'object' ? payload : null
  const data = body && typeof body.data === 'object' && body.data !== null ? body.data : body
  if (!data) return { ...UNKNOWN, reason: 'no_payload' }
  if (body && body.status && body.status !== 'ok') {
    return { ...UNKNOWN, reason: 'ledger_error' }
  }
  const balance = Number(data.balance)
  if (!Number.isFinite(balance) || balance < 0) {
    return { ...UNKNOWN, reason: 'balance_missing' }
  }
  const allotment = Number(data.allotment)
  const consumed = Number(data.consumed)
  return {
    ok: true,
    reason: '',
    balance,
    allotment: Number.isFinite(allotment) ? allotment : null,
    consumed: Number.isFinite(consumed) ? consumed : null,
    plan: typeof data.plan === 'string' ? data.plan : '',
    period: typeof data.period === 'string' ? data.period : '',
  }
}

/**
 * Can this action be run? Returns `{ ok, reason, message, shortfall }`.
 *
 * An unreadable meter is never treated as "affordable": the run is blocked with
 * the reason, because a generation that cannot be priced cannot be promised.
 */
export function affordability(meter, cost = AI_DESIGN_COST) {
  const price = Number(cost)
  if (!meter || meter.ok !== true) {
    return {
      ok: false,
      reason: 'meter_unavailable',
      shortfall: null,
      message: 'Credit balance unavailable — the meter could not be read. Retry, or open Account to check the plan.',
    }
  }
  if (!Number.isFinite(price) || price <= 0) {
    return { ok: false, reason: 'bad_price', shortfall: null, message: 'This action has no valid price.' }
  }
  if (meter.balance < price) {
    const shortfall = Math.round((price - meter.balance) * 100) / 100
    return {
      ok: false,
      reason: 'insufficient',
      shortfall,
      message: `This run costs ${price} credits and ${meter.balance} remain — ${shortfall} short. Top up or upgrade to continue.`,
    }
  }
  return { ok: true, reason: '', shortfall: 0, message: '' }
}

/** One honest line for the sidebar: price, balance and where it came from. */
export function meterLine(meter, cost = AI_DESIGN_COST) {
  if (!meter || meter.ok !== true) {
    return `AI Design = ${cost} credits · balance unavailable`
  }
  const plan = meter.plan ? ` on ${meter.plan}` : ''
  const left = meter.allotment === null ? `${meter.balance}` : `${meter.balance} of ${meter.allotment}`
  return `AI Design = ${cost} credits · ${left} left${plan}`
}

/**
 * Turn a thrown request error into something an operator can act on.
 *
 * The pages used to print `e.message` verbatim, so "http_500" and
 * "Failed to fetch" were the entire error UI. Every branch here names what
 * happened and what to do next.
 */
export function describeError(error) {
  const status = error && typeof error.status === 'number' ? error.status : 0
  const code = (error && (error.code || '')) || ''
  if (status === 401 || status === 403) {
    return { tone: 'auth', action: 'sign_in', message: 'Your session has expired — sign in again, then retry.' }
  }
  if (status === 429 || code === 'rate_limited') {
    return { tone: 'retry', action: 'retry', message: 'The engine is rate limiting this account — wait a moment and retry.' }
  }
  if (status === 0) {
    return { tone: 'offline', action: 'retry', message: 'The local engine is unreachable — nothing was generated. Start the engine, then retry.' }
  }
  if (status >= 500) {
    return { tone: 'server', action: 'retry', message: `The engine failed (${status}) — nothing was saved. Retry, and if it repeats check the engine log.` }
  }
  const detail = (error && error.message) || `http_${status}`
  return { tone: 'request', action: 'edit', message: `The request was rejected: ${detail}. Adjust the brief and retry.` }
}
