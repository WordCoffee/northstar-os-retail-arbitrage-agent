import { ok, err, internalError } from "../_envelope.js";

export async function onRequestGet(context) {
  const { params, env } = context;
  const fileName = params.filename;

  if (!fileName || !fileName.endsWith(".json")) {
    return err("invalid_request", "Invalid file name.", "sourcescout");
  }

  try {
    const raw = await env.DEALS_KV.get(`scored:${fileName}`);
    if (!raw) {
      return err("not_found", "File not found.", "sourcescout");
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      return internalError("sourcescout");
    }
    return ok({ name: fileName, data: parsed }, "sourcescout");
  } catch (e) {
    return internalError("sourcescout");
  }
}