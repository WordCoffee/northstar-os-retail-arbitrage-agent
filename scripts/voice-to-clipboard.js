#!/usr/bin/env node
/**
 * Voice-to-Clipboard — record a voice prompt and transcribe it with local whisper.cpp
 *
 * Modes:
 *   default  : record → transcribe → copy transcript to Windows clipboard (human output)
 *   --json   : record → transcribe → print {"ok":true,"text":"..."} to stdout (for OpenCode plugin)
 *
 * Pipeline (all local, offline, no API costs):
 *   sox.exe (SoX_ng)      → record WAV from default mic, stop on silence
 *   whisper-cli.exe       → transcribe with ggml-base.en.bin
 *   clip.exe              → copy result to clipboard (default mode only)
 *
 * Config (env vars):
 *   NS_SOX_PATH           → sox binary        (default: %USERPROFILE%\whisper-tools\sox.exe)
 *   NS_WHISPER_CLI        → whisper-cli       (default: %USERPROFILE%\whisper-tools\whisper-cli.exe)
 *   NS_WHISPER_MODEL      → ggml model        (default: %USERPROFILE%\.local\share\whisper-cpp\ggml-base.en.bin)
 *   NS_WHISPER_VAD        → silero VAD model  (default: %USERPROFILE%\.local\share\whisper-cpp\ggml-silero-v6.2.0.bin)
 *   NS_VOICE_MAX_SECONDS  → max recording     (default: 25)
 *
 * Usage:
 *   node scripts/voice-to-clipboard.js            # clipboard mode
 *   node scripts/voice-to-clipboard.js --json     # machine-readable mode
 */

import { spawn } from 'node:child_process';
import { access } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const HELP = `Voice-to-Clipboard — record a prompt and transcribe it with local whisper.cpp

Usage:
  node voice-to-clipboard.js [--json] [--help] [--file <wav>]

  --json   Print {"ok":true,"text":"..."} to stdout (no clipboard). Used by the OpenCode plugin.
  --file   Test hook: transcribe an existing WAV instead of recording (no mic needed).
  --help   Show this help.

Env:
  NS_SOX_PATH, NS_WHISPER_CLI, NS_WHISPER_MODEL, NS_WHISPER_VAD, NS_VOICE_MAX_SECONDS
`;

const args = process.argv.slice(2);
if (args.includes('--help') || args.includes('-h')) {
  console.log(HELP);
  process.exit(0);
}
const jsonMode = args.includes('--json');
// Hidden test hook: transcribe a pre-made WAV instead of recording (no mic required).
const fileArgIndex = args.indexOf('--file');
const FILE_ARG = fileArgIndex >= 0 ? args[fileArgIndex + 1] : null;

const USERPROFILE = process.env.USERPROFILE || process.env.HOME || '';
const SOX = process.env.NS_SOX_PATH || path.join(USERPROFILE, 'whisper-tools', 'sox.exe');
const WHISPER_CLI = process.env.NS_WHISPER_CLI || path.join(USERPROFILE, 'whisper-tools', 'whisper-cli.exe');
const WHISPER_MODEL =
  process.env.NS_WHISPER_MODEL || path.join(USERPROFILE, '.local/share/whisper-cpp/ggml-base.en.bin');
const WHISPER_VAD =
  process.env.NS_WHISPER_VAD || path.join(USERPROFILE, '.local/share/whisper-cpp/ggml-silero-v6.2.0.bin');
const MAX_SECONDS = Number(process.env.NS_VOICE_MAX_SECONDS || 25);

const TEMP_DIR = os.tmpdir();

/** Exit with an error. JSON mode → JSON on stdout; human mode → stderr. */
function fail(message, code = 1) {
  if (jsonMode) {
    process.stdout.write(JSON.stringify({ ok: false, error: message }) + '\n');
  } else {
    process.stderr.write(`\n❌ ${message}\n`);
  }
  process.exit(code);
}

function log(message) {
  if (!jsonMode) process.stderr.write(message + '\n');
}

function exists(p) {
  return access(p)
    .then(() => true)
    .catch(() => false);
}

/** Run a command, collect stdout/stderr, kill after timeoutMs. */
function run(bin, binArgs, { timeoutMs }) {
  return new Promise((resolve) => {
    const child = spawn(bin, binArgs, { windowsHide: true });
    let stdout = '';
    let stderr = '';
    let settled = false;

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        child.kill();
        resolve({ code: null, timeout: true, stdout, stderr });
      }
    }, timeoutMs);

    child.stdout.on('data', (d) => (stdout += d.toString()));
    child.stderr.on('data', (d) => (stderr += d.toString()));
    child.on('error', (err) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve({ code: null, timeout: false, error: err.message, stdout, stderr });
      }
    });
    child.on('close', (code) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve({ code, timeout: false, stdout, stderr });
      }
    });
  });
}

/** sox: record from default device until silence (0.8s) or the Node-side cap. */
async function record(seconds) {
  const wavPath = path.join(TEMP_DIR, `ns-voice-${Date.now()}.wav`);
  const args = [
    '--default-device',
    '--channels',
    '1',
    '--rate',
    '16000',
    '--type',
    'wav',
    wavPath,
    'silence',
    '1',
    '0.1',
    '2%',
    '1',
    '0.8',
    '3%',
  ];

  log(`🎤 Listening (max ${seconds}s)... speak, then pause. Ctrl+C to cancel.`);
  // Node-side cap: sox keeps listening if the room is noisy, so kill it past the limit.
  const result = await run(SOX, args, { timeoutMs: seconds * 1000 + 8000 });

  if (result.timeout) log('⏱️ Recording cap reached — processing now.');
  if (result.error) throw new Error(`sox failed to start: ${result.error}`);
  if (result.code !== 0) {
    const hint = (result.stderr || '').split('\n').filter(Boolean).slice(-3).join(' | ');
    throw new Error(`sox exited with code ${result.code}${hint ? ` — ${hint}` : ''}`);
  }
  return wavPath;
}

/** whisper-cli: transcribe the WAV (same proven flags as the Northstar voice server). */
async function transcribe(wavPath) {
  const args = ['-m', WHISPER_MODEL, '-f', wavPath, '-l', 'en', '-nt', '--print-special', 'false'];
  if (await exists(WHISPER_VAD)) args.push('-vm', WHISPER_VAD);

  let result = await run(WHISPER_CLI, args, { timeoutMs: 120000 });
  if (result.timeout) throw new Error('whisper-cli timed out');
  if (result.error) throw new Error(`whisper-cli failed to start: ${result.error}`);

  if (result.code !== 0 && args.includes('-vm')) {
    // Retry without VAD once (mirrors the voice server behavior).
    const retryArgs = args.filter((a) => a !== '-vm').slice(0, args.indexOf('-vm'));
    result = await run(WHISPER_CLI, retryArgs, { timeoutMs: 120000 });
  }
  if (result.code !== 0) {
    const hint = (result.stderr || '').split('\n').filter(Boolean).slice(-3).join(' | ');
    throw new Error(`whisper-cli exited with code ${result.code}${hint ? ` — ${hint}` : ''}`);
  }
  return parseWhisperOutput(result.stdout);
}

/** Strip timestamps/special-token/noise-tag garbage from whisper stdout. */
function parseWhisperOutput(output) {
  const singleToks = new Set(['.', '..', '...', ',', '?', '!']);
  const starts = ['[', 'whisper_', 'system_info', 'main:'];
  const noise = ['[EMPTY]', '[ Sound Effects ]', '[MUSIC', '[BLANK', '[SILENCE', '[NO_SPEECH'];
  const lines = output
    .split('\n')
    .map((l) => l.replace(/<\|[^|]+\|>/g, '').trim())
    .filter((t) => {
      if (!t || singleToks.has(t) || /^\([^)]*\)$/.test(t)) return false;
      return !starts.some((s) => t.startsWith(s)) && !noise.some((n) => t.includes(n));
    });
  return lines.join(' ').trim();
}

/** Copy text to the Windows clipboard via clip.exe. */
function toClipboard(text) {
  return new Promise((resolve, reject) => {
    const clip = spawn('clip.exe', [], { windowsHide: true, stdio: ['pipe', 'ignore', 'ignore'] });
    let err = '';
    clip.stderr?.on('data', (d) => (err += d.toString()));
    clip.on('error', (e) => reject(new Error(`clip.exe failed: ${e.message}`)));
    clip.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`clip.exe exited with ${code}${err ? ` — ${err}` : ''}`))));
    clip.stdin.write(text);
    clip.stdin.end();
  });
}

async function main() {
  // 1. Prerequisite checks
  for (const [label, p] of [
    ['whisper-cli', WHISPER_CLI],
    ['whisper model', WHISPER_MODEL],
    ['sox', SOX],
  ]) {
    if (!(await exists(p))) fail(`Missing ${label}: ${p} — set NS_* paths or install the tool.`);
  }

  let wavPath = null;
  try {
    if (FILE_ARG) {
      // Test hook: validate whisper + parsing on an existing file (skips mic capture).
      log(`🧠 Transcribing ${FILE_ARG}...`);
      const text = await transcribe(FILE_ARG);
      if (!text) throw new Error('No speech detected — test WAV produced no transcript.');
      if (jsonMode) {
        process.stdout.write(JSON.stringify({ ok: true, text }) + '\n');
      } else {
        log(`✅ Transcript: ${text}`);
      }
      return;
    }

    // 2. Record
    log('');
    wavPath = await record(MAX_SECONDS);
    const stat = await import('node:fs/promises').then((m) => m.stat(wavPath));
    if (stat.size < 1000) throw new Error('Recording was empty — no audio captured (mic muted?)');

    // 3. Transcribe
    log('🧠 Transcribing...');
    const text = await transcribe(wavPath);
    if (!text) throw new Error('No speech detected — try again and speak louder/clearer.');

    // 4. Deliver
    if (!jsonMode) {
      await toClipboard(text);
      log('');
      log(`✅ Copied to clipboard:`);
      log(`   ${text}`);
    } else {
      process.stdout.write(JSON.stringify({ ok: true, text }) + '\n');
    }
  } catch (err) {
    fail(`Voice input failed: ${err.message}`, 1);
  } finally {
    if (wavPath) {
      const { unlink } = await import('node:fs/promises');
      unlink(wavPath).catch(() => {});
    }
  }
}

main();