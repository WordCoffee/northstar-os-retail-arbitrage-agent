import { loadLatestDeals } from "../../src/lib/dealsApi.js";
import { ok, internalError } from "./_envelope.js";

export async function onRequestGet(context) {
  try {
    const data = await loadLatestDeals(context.env);
    return ok(data, "sourcescout");
  } catch (e) {
    // Never leak the raw provider/storage error — no-leak boundary (BFF §6).
    return internalError("sourcescout");
  }
}