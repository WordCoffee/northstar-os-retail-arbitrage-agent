/**
 * Voice Transcription Server - CommonJS Version
 * 
 * Accepts raw audio data via POST and returns transcribed text.
 */

const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs/promises');
const os = require('os');

const app = express();
const PORT = process.env.VOICE_SERVER_PORT || 3001;

// Paths
const WHISPER_TOOLS = path.join(process.env.USERPROFILE || '/home/user', 'whisper-tools');
const WHISPER_MODEL = path.join(process.env.USERPROFILE || '/home/user', '.local/share/whisper-cpp/ggml-base.en.bin');
const WHISPER_VAD = path.join(process.env.USERPROFILE || '/home/user', '.local/share/whisper-cpp/ggml-silero-v6.2.0.bin');
const TEMP_DIR = os.tmpdir();

app.use(express.raw({ type: ['audio/*', 'application/octet-stream'], limit: '20mb' }));
app.use(express.json({ limit: '10mb' }));

console.log('Express app created');

// Health check
app.get('/health', (req, res) => {
  console.log('Health check hit');
  res.json({ status: 'ok', whisper_cli: WHISPER_TOOLS });
});

// Main transcription endpoint - accepts raw audio
app.post('/api/voice-transcribe', async (req, res) => {
  console.log('POST /api/voice-transcribe hit, body length:', req.body?.length);
  try {
    const audioBuffer = req.body;
    
    if (!audioBuffer || audioBuffer.length === 0) {
      return res.status(400).json({ status: 'error', error: 'No audio data' });
    }

    // Save to temp WAV file
    const timestamp = Date.now();
    const tempWavPath = path.join(TEMP_DIR, `voice-${timestamp}.wav`);
    await fs.writeFile(tempWavPath, audioBuffer);
    console.log('Saved audio to:', tempWavPath);

    try {
      // Transcribe using whisper-cli
      const transcription = await transcribeWithWhisper(tempWavPath);
      res.json({ status: 'ok', text: transcription });
    } finally {
      // Cleanup
      try { await fs.unlink(tempWavPath); } catch (e) {}
    }

  } catch (error) {
    console.error('Transcription error:', error);
    res.status(500).json({ status: 'error', error: error.message });
  }
});

function transcribeWithWhisper(wavPath) {
  return new Promise((resolve, reject) => {
    const whisperCli = path.join(WHISPER_TOOLS, 'whisper-cli.exe');
    console.log('Running whisper-cli:', whisperCli);
    
    const args = [
      '-m', WHISPER_MODEL,
      '-f', wavPath,
      '-l', 'en',
      '-nt',
      '--print-special', 'false'
    ];

    // Add VAD if available
    try {
      fs.accessSync(WHISPER_VAD);
      args.push('-vm', WHISPER_VAD);
      console.log('Using VAD:', WHISPER_VAD);
    } catch (e) {
      console.log('VAD not available, skipping');
    }

    const process = spawn(whisperCli, args, { shell: true });
    
    let output = '';
    let stderr = '';

    process.stdout.on('data', (data) => {
      output += data.toString();
    });

    process.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    process.on('close', (code) => {
      console.log('whisper-cli exited with code:', code);
      if (code !== 0) {
        // Try without VAD
        if (args.includes('-vm')) {
          console.log('Retrying without VAD');
          transcribeWithoutVAD(wavPath).then(resolve).catch(reject);
        } else {
          reject(new Error(`whisper-cli exited with code ${code}: ${stderr}`));
        }
        return;
      }
      
      const text = parseWhisperOutput(output);
      console.log('Transcription result:', text);
      resolve(text);
    });
  });
}

function transcribeWithoutVAD(wavPath) {
  return new Promise((resolve, reject) => {
    const whisperCli = path.join(WHISPER_TOOLS, 'whisper-cli.exe');
    
    const args = [
      '-m', WHISPER_MODEL,
      '-f', wavPath,
      '-l', 'en',
      '-nt',
      '--print-special', 'false'
    ];

    const process = spawn(whisperCli, args, { shell: true });
    
    let output = '';
    let stderr = '';

    process.stdout.on('data', (data) => {
      output += data.toString();
    });

    process.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    process.on('close', (code) => {
      console.log('whisper-cli (no VAD) exited with code:', code);
      if (code !== 0) {
        reject(new Error(`whisper-cli exited with code ${code}: ${stderr}`));
        return;
      }
      
      const text = parseWhisperOutput(output);
      console.log('Transcription result:', text);
      resolve(text);
    });
  });
}

function parseWhisperOutput(output) {
  const lines = output.split('\n')
    .filter(line => {
      const trimmed = line.trim();
      return trimmed &&
        !trimmed.startsWith('[') &&
        !trimmed.startsWith('whisper_') &&
        !trimmed.startsWith('system_info') &&
        !trimmed.startsWith('main:') &&
        trimmed !== '.' &&
        trimmed !== '..' &&
        trimmed !== '...' &&
        trimmed !== ',' &&
        trimmed !== '?' &&
        trimmed !== '!' &&
        !trimmed.includes('[EMPTY]') &&
        !trimmed.includes('[ Sound Effects ]') &&
        !trimmed.includes('[MUSIC') &&
        !trimmed.includes('[BLANK') &&
        !trimmed.includes('[SILENCE') &&
        !trimmed.includes('[NO_SPEECH');
    })
    .map(l => l.trim());
  
  return lines.join(' ').trim();
}

// Start server
console.log('Calling app.listen...');
const server = app.listen(PORT, '127.0.0.1', () => {
  console.log(`\n🎤 Voice Transcription Server`);
  console.log(`   Server: http://127.0.0.1:${PORT}`);
  console.log(`   POST /api/voice-transcribe (raw audio)`);
  console.log(`   GET  /health`);
  console.log(`\n   Whisper: ${WHISPER_TOOLS}\\whisper-cli.exe`);
  console.log(`   Model:   ${WHISPER_MODEL}`);
  console.log('');
  console.log('Server is ready!');
});

server.on('error', (err) => {
  console.error('Server error:', err);
});

module.exports = app;