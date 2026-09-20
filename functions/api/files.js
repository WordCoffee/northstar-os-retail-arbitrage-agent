import { ok, empty, internalError } from "./_envelope.js";

export async function onRequestGet(context) {
  const { env } = context;
  try {
    const raw = await env.DEALS_KV.get("scored:index");
    if (raw === null || raw === undefined) {
      const data = { files: [] };
      return empty(data, "sourcescout");
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      // KV returned malformed index — treat as empty, never leak the value.
      return empty({ files: [] }, "sourcescout");
    }
    return ok({ files: parsed }, "sourcescout");
  } catch (e) {
    return internalError("sourcescout");
  }
}