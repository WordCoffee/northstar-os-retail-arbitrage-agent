import { ok, internalError } from "./_envelope.js";

/**
 * Public health/uptime endpoint (Phase E1).
 *
 * Returns a bff/v1 envelope so an uptime probe (or Cloudflare health check)
 * can assert `status:"ok"`. Intentionally unauthenticated: it exposes only
 * liveness + binding presence, never secrets, providers, or internal paths.
 * The meta.service key is "health"; no provider/vendor identifiers appear.
 */
export async function onRequestGet(context) {
  const { env } = context;
  try {
    const kvBound = !!(env && env.DEALS_KV);
    return ok({
      status: "ok",
      service: "northstar-pages-functions",
      kv_bound: kvBound,
      time: new Date().toISOString(),
    }, "health");
  } catch (e) {
    // Never leak exception text (BFF §6).
    return internalError("health");
  }
}
