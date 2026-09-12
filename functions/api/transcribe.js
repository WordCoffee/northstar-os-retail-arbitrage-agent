/**
 * API endpoint for speech-to-text transcription
 * Proxies to local whisper.cpp service
 *
 * POST /api/transcribe
 * Body: FormData with 'audio' field (audio/webm or audio/wav)
 *
 * Response: { text: "transcribed text" }
 */

export async function onRequest(context) {
  const { request, env } = context;

  if (request.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const formData = await request.formData();
    const audioFile = formData.get('audio');

    if (!audioFile) {
      return new Response(JSON.stringify({ error: 'No audio file provided' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Save to temp location
    const tempDir = env.TMP_DIR || '/tmp';
    const tempPath = `${tempDir}/voice_${Date.now()}.wav`;

    // In a real Cloudflare Worker, you'd use R2 or a KV store
    // For local development, you can read the file buffer and save locally

    // Placeholder: Return a message indicating setup is needed
    // In production, this would:
    // 1. Save the audio file to disk
    // 2. Call whisper-cli via a spawned process or API
    // 3. Return the transcription

    return new Response(JSON.stringify({
      text: '',
      info: 'This endpoint needs to be deployed with a backend that can invoke whisper-cli'
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

/**
 * Local version for Node.js / standalone backend
 * Run with: node functions/api/local-transcribe.js
 *
 * This uses whisper.cpp locally
 */
if (typeof process !== 'undefined' && import.meta.url === `file://${process.argv[1]}`) {
  const fs = await import('node:fs');
  const path = await import('node:path');
  const { spawn } = await import('node:child_process');

  // ... implementation for local transcription
}
