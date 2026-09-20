/**
 * Speech-to-text transcription endpoint.
 *
 * STATUS: NOT IMPLEMENTED (B5, aligned with bff/v1 error taxonomy).
 * This route intentionally returns HTTP 501 `not_implemented` for every
 * request. Earlier builds returned a fake success ({text: ""}); that is
 * dishonest and removed. Real transcription requires a whisper-class backend
 * with explicit operator approval for the deployed environment — out of scope
 * for the current Pages + Functions deployment.
 */

import { err, notImplemented } from "./_envelope.js";

export async function onRequest(context) {
  const { request } = context;

  if (request.method !== "POST") {
    return err("invalid_request", "Method not allowed.", "autothink");
  }

  return notImplemented("autothink");
}