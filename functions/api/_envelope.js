/**
 * bff/v1 response envelope helper for Cloudflare Pages Functions (B5).
 *
 * Aligns every Functions response with docs/contracts/BFF_CONTRACT_v1.md:
 * uniform `contract`/`request_id`/`status`/`data`/`error`/`meta` envelope,
 * honest error taxonomy (incl. `not_implemented` = 501), and no-leak rule
 * (generic messages only — never raw provider/exception text).
 *
 * Underscore-prefixed files are NOT treated as routes by Pages Functions.
 */

const JSON_HEADERS = { "Content-Type": "application/json" };

function reqId() {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  let hex = "";
  for (const x of b) hex += x.toString(16).padStart(2, "0");
  return "req_" + hex;
}

const HTTP_FOR = {
  ok: 200,
  empty: 200,
  invalid_request: 400,
  unauthorized: 401,
  forbidden: 403,
  entitlement_required: 403,
  not_found: 404,
  conflict: 409,
  not_implemented: 501,
  provider_unavailable: 502,
  internal_error: 500,
};

function respond(status, error, data, service) {
  return new Response(JSON.stringify({
    contract: "bff/v1",
    request_id: reqId(),
    status,
    data: status === "error" ? null : (data === undefined ? null : data),
    error: status === "error" ? error : null,
    meta: { service: service || "unknown", version: "v1" },
  }), {
    status: HTTP_FOR[status === "error" ? error.code : status] || 500,
    headers: JSON_HEADERS,
  });
}

export function ok(data, service) {
  return respond("ok", null, data, service);
}

export function empty(data, service) {
  return respond("empty", null, data === undefined ? {} : data, service);
}

/** Standard error responses by contract code (message reaches clients). */
export function err(code, message, service) {
  return respond("error", {
    code,
    message,
    retryable: code === "provider_unavailable" || code === "rate_limited",
    details: null,
  }, null, service);
}

export function internalError(service) {
  // Never leak exception text — this is the no-leak boundary (BFF §6).
  return err("internal_error", "An unexpected server error occurred.", service);
}

export function notImplemented(service) {
  return err("not_implemented", "This endpoint is not yet implemented.", service);
}
