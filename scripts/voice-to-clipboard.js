#!/usr/bin/env node
/**
 * Voice Capture+Transcribe — record a voice prompt and transcribe it with local whisper.cpp
 *
 * Recording model: NON-STOP. No silence detection — the capture keeps running until:
 *   - you press Enter in the terminal (standalone use), or
 *   - stdin is closed by the caller (OpenCode plugin sends the stop signal), or
 *   - the max-seconds cap is reached (default 30s, safety net for "no audio").
 *
 * Modes:
 *   default        : record → transcribe → copy to Windows clipboard (human output)
 *   --json         : same record→transcribe, print {"ok":true,"text":"..."} to stdout
 *   --record <wav> : record only; write a valid 16kHz mono 16-bit WAV to <wav>; exit
 *   --file <wav>   : transcribe an existing WAV (skip recording)
 *   --help         : show help
 *
 * Pipeline (all local, offline, no API costs):
 *   sox.exe (SoX_ng)  → record RAW PCM from default mic (sox can be killed safely mid-capture;
 *                       the script wraps the raw stream in a WAV header afterwards)
 *   whisper-cli.exe   → transcribe with ggml-base.en.bin (multi-threaded)
 *   clip.exe          → copy result to clipboard (default mode only)
 *
 * Config (env vars):
 *   NS_SOX_PATH, NS_WHISPER_CLI, NS_WHISPER_MODEL, NS_WHISPER_VAD, NS_VOICE_MAX_SECONDS
 *   (defaults point at %USERPROFILE%\whisper-tools\ and %USERPROFILE%\.local\share\whisper-cpp\)
 */

import { spawn } from 'node:child_process';
import { access, readFile, writeFile, unlink, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const HELP = `Voice Capture+Transcribe — record a prompt with your mic, transcribe with local whisper.cpp

Usage:
  node voice-to-clipboard.js [--json] [--record <wav>] [--file <wav>] [--help]

  (no flags)   Record until Enter/cap → transcribe → copy to clipboard.
  --json       Same, but print {"ok":true,"text":"..."} to stdout (OpenCode plugin mode).
  --record     Record only; write a 16kHz mono WAV, then exit (OpenCode plugin records this way).
  --file       Transcribe an existing WAV (no recording).
  --help       Show this help.

Recording stops when: you press Enter (terminal), the caller closes stdin (plugin), or
the cap is reached (NS_VOICE_MAX_SECONDS, default 30).

Env: NS_SOX_PATH, NS_WHISPER_CLI, NS_WHISPER_MODEL, NS_WHISPER_VAD, NS_VOICE_MAX_SECONDS
`;

const args = process.argv.slice(2);
if (args.includes('--help') || args.includes('-h')) {
  console.log(HELP);
  process.exit(0);
}
const jsonMode = args.includes('--json');
const fileIdx = args.indexOf('--file');
const FILE_ARG = fileIdx >= 0 ? args[fileIdx + 1] : null;
const recIdx = args.indexOf('--record');
const RECORD_ARG = recIdx >= 0 ? args[recIdx + 1] : null;

const USERPROFILE = process.env.USERPROFILE || process.env.HOME || '';
const SOX = process.env.NS_SOX_PATH || path.join(USERPROFILE, 'whisper-tools', 'sox.exe');
const WHISPER_CLI = process.env.NS_WHISPER_CLI || path.join(USERPROFILE, 'whisper-tools', 'whisper-cli.exe');
const WHISPER_MODEL =
  process.env.NS_WHISPER_MODEL || path.join(USERPROFILE, '.local/share/whisper-cpp/ggml-base.en.bin');
const WHISPER_VAD =
  process.env.NS_WHISPER_VAD || path.join(USERPROFILE, '.local/share/whisper-cpp/ggml-silero-v6.2.0.bin');
const MAX_SECONDS = Number(process.env.NS_VOICE_MAX_SECONDS || 30);
const THREADS = Math.min(os.availableParallelism ? os.availableParallelism() : 4, 16);
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

/** Build a canonical 16-bit PCM WAV header for `dataLength` payload bytes. */
function wavHeader(dataLength, sampleRate = 16000, channels = 1, bitsPerSample = 16) {
  const blockAlign = (channels * bitsPerSample) / 8;
  const byteRate = sampleRate * blockAlign;
  const buf = Buffer.alloc(44);
  buf.write('RIFF', 0);
  buf.writeUInt32LE(36 + dataLength, 4);
  buf.write('WAVE', 8);
  buf.write('fmt ', 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); // PCM
  buf.writeUInt16LE(channels, 22);
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(byteRate, 28);
  buf.writeUInt16LE(blockAlign, 32);
  buf.writeUInt16LE(bitsPerSample, 34);
  buf.write('data', 36);
  buf.writeUInt32LE(dataLength, 40);
  return buf;
}

/**
 * Record RAW PCM (16kHz mono) to <wavPath>.raw, then wrap it in a real WAV and
 * resolve with the final path. Stops on Enter/stin-EOF/max-seconds.
 * sox is killed mid-capture — RAW has no header to corrupt, so this is safe.
 */
function recordRaw(wavPath, maxSeconds) {
  const rawPath = wavPath + '.raw';
  return new Promise((resolve, reject) => {
    const args = [
      '--default-device',
      '--channels',
      '1',
      '--rate',
      '16000',
      '--type',
      'raw',
      rawPath,
      'trim',
      '0',
      String(maxSeconds),
    ];
    const child = spawn(SOX, args, { windowsHide: true });
    let done = false;
    let hardTimer = null;
    const startedAt = Date.now();

    const progress = setInterval(() => {
      const el = Math.round((Date.now() - startedAt) / 1000);
      log(`⏱️ ${el}s / ${maxSeconds}s — speak now, press Enter when done.`);
    }, 1000);

    const finish = () => {
      if (done) return;
      done = true;
      clearInterval(progress);
      if (hardTimer) clearTimeout(hardTimer);
      process.stdin.removeAllListeners('data');
      process.stdin.removeAllListeners('end');
      child.kill();
    };

    const wrap = async () => {
      try {
        const data = await readFile(rawPath);
        const audio = data.length % 2 ? data.subarray(0, data.length - 1) : data;
        await writeFile(wavPath, Buffer.concat([wavHeader(audio.length), audio]));
        await unlink(rawPath).catch(() => {});
        resolve(wavPath);
      } catch (e) {
        reject(new Error(`Failed to finalize recording: ${e.message}`));
      }
    };

    child.on('error', (e) => {
      if (done) return;
      finish();
      reject(new Error(`sox failed to start: ${e.message} (mic available?)`));
    });
    child.on('close', () => {
      finish();
      wrap();
    });

    // Hard cap even if stdin never fires (forgotten recording / no-audio case).
    hardTimer = setTimeout(() => finish(), maxSeconds * 1000 + 5000);

    // Stop triggers: Enter in a terminal, or the caller closing stdin.
    process.stdin.resume();
    process.stdin.on('data', () => finish());
    process.stdin.on('end', () => finish());
  });
}

/** whisper-cli: transcribe the WAV (threaded; same proven flags as the Northstar voice server). */
async function transcribe(wavPath) {
  const args = ['-m', WHISPER_MODEL, '-f', wavPath, '-l', 'en', '-nt', '--print-special', 'false', '-t', String(THREADS)];
  if (await exists(WHISPER_VAD)) args.push('-vm', WHISPER_VAD);

  let result = await run(WHISPER_CLI, args, { timeoutMs: 120000 });
  if (result.timeout) throw new Error('whisper-cli timed out');
  if (result.error) throw new Error(`whisper-cli failed to start: ${result.error}`);

  if (result.code !== 0 && args.includes('-vm')) {
    // Retry without VAD once (mirrors the voice server behavior).
    const vIdx = args.indexOf('-vm');
    const retryArgs = args.slice(0, vIdx);
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
    clip.on('close', (code) =>
      code === 0 ? resolve() : reject(new Error(`clip.exe exited with ${code}${err ? ` — ${err}` : ''}`)),
    );
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

  // 2. Record-only mode (used by the OpenCode plugin; exits cleanly after writing the WAV)
  if (RECORD_ARG) {
    log('');
    log(`🎤 Recording… speak now. Press Enter when done. (max ${MAX_SECONDS}s)`);
    const wavPath = await recordRaw(RECORD_ARG, MAX_SECONDS);
    const info = await stat(wavPath);
    if (info.size - 44 < 4000) throw new Error('Recording too short — press Enter after speaking.');
    process.exit(0);
  }

  // 3. Transcribe-only mode (test hook / plugin transcription step)
  if (FILE_ARG) {
    const text = await transcribe(FILE_ARG);
    if (!text) fail('No speech detected — try again and speak louder/clearer.', 2);
    if (jsonMode) {
      process.stdout.write(JSON.stringify({ ok: true, text }) + '\n');
    } else {
      console.log(`Transcript: ${text}`);
    }
    process.exit(0);
  }

  // 4. Default: record → transcribe → clipboard
  let wavPath = null;
  try {
    log('');
    log(`🎤 Recording… speak now. Press Enter when done. (max ${MAX_SECONDS}s)`);
    wavPath = await recordRaw(path.join(TEMP_DIR, `ns-voice-${Date.now()}.wav`), MAX_SECONDS);
    const info = await stat(wavPath);
    if (info.size - 44 < 4000) throw new Error('Recording too short — press Enter after speaking.');

    log('🧠 Transcribing...');
    const text = await transcribe(wavPath);
    if (!text) throw new Error('No speech detected — try again and speak louder/clearer.');

    if (!jsonMode) {
      await toClipboard(text);
      log('');
      log(`✅ Copied to clipboard: ${text}`);
    } else {
      process.stdout.write(JSON.stringify({ ok: true, text }) + '\n');
    }
  } catch (err) {
    fail(`Voice input failed: ${err.message}`, 1);
  } finally {
    if (wavPath) unlink(wavPath).catch(() => {});
  }
}

main();