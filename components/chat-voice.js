/**
 * Chat Voice Integration Module
 * 
 * Adds voice recording buttons to chat input boxes.
 * When clicked, records audio, transcribes via local whisper, and
 * inserts the transcript into the chat input.
 *
 * Supported modes:
 * - local: Uses local server (server/voice-transcribe.js)
 * - batch: Uses voice.bat script directly (requires Node backend)
 * - api: Uses external API (Groq/DeepSeek/etc.)
 *
 * Usage:
 *   import { attachVoiceToChat } from '/components/chat-voice.js';
 *   attachVoiceToChat('.chat-input-container', { serverUrl: 'https://voice.example.com' });
 */

class ChatVoiceWidget {
  constructor(options = {}) {
    this.options = {
      serverUrl: options.serverUrl || null,
      model: options.model || 'local',
      duration: options.duration || 300, // 5 minutes max
      onTranscribed: options.onTranscribed || null,
      onError: options.onError || null,
      ...options
    };

    this.isRecording = false;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.stream = null;
  }

  /**
   * Attach voice button to a chat input container
   * @param {string} containerSelector - CSS selector for chat input container
   * @param {object} options - Configuration options
   */
  static attach(containerSelector, options = {}) {
    const container = document.querySelector(containerSelector);
    if (!container) {
      console.warn(`ChatVoiceWidget: Container '${containerSelector}' not found`);
      return null;
    }

    return new ChatVoiceWidget({
      ...options,
      container: container
    });
  }

  /**
   * Initialize widget for a specific container
   */
  async init(container) {
    this.container = container;
    this.createVoiceButton();
    this.attachEvents();
    return this;
  }

  /**
   * Create the voice recording button
   */
  createVoiceButton() {
    if (!this.container) return;

    // Create voice button
    this.voiceBtn = document.createElement('button');
    this.voiceBtn.type = 'button';
    this.voiceBtn.className = 'ns-chat-voice-btn';
    this.voiceBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
        <path d="M12 19v3"></path>
      </svg>
    `;
    this.voiceBtn.title = 'Click to record voice';

    // Create status indicator
    this.statusIndicator = document.createElement('span');
    this.statusIndicator.className = 'ns-voice-status-indicator';
    this.statusIndicator.style.display = 'none';

    // Find the input field in the container
    this.inputField = this.container.querySelector('input[type="text"], textarea, .chat-input');
    if (!this.inputField) {
      this.inputField = this.container.querySelector('.input-field, input, textarea');
    }

    // Insert voice button after the input field or at end of container
    if (this.inputField && this.inputField.parentNode) {
      this.inputField.parentNode.insertBefore(this.voiceBtn, this.inputField.nextSibling);
      this.inputField.parentNode.insertBefore(this.statusIndicator, this.voiceBtn.nextSibling);
    } else {
      this.container.appendChild(this.voiceBtn);
      this.container.appendChild(this.statusIndicator);
    }

    // Add styles
    this.injectStyles();
  }

  /**
   * Inject CSS styles for the voice button
   */
  injectStyles() {
    if (document.getElementById('ns-chat-voice-styles')) return;

    const styles = `
      .ns-chat-voice-btn {
        background: #3b82f6;
        color: white;
        border: none;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
        margin-left: 8px;
        flex-shrink: 0;
      }
      .ns-chat-voice-btn:hover {
        background: #2563eb;
        transform: scale(1.05);
      }
      .ns-chat-voice-btn.recording {
        background: #ef4444;
        animation: ns-record-pulse 1s infinite;
      }
      .ns-chat-voice-btn svg { display: block; }
      .ns-voice-status-indicator {
        font-size: 11px;
        color: #94a3b8;
        margin-left: 8px;
      }
      .ns-voice-status-indicator.recording { color: #ef4444; }
      .ns-voice-status-indicator.transcribing { color: #3b82f6; }
      @keyframes ns-record-pulse {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
      }
    `;

    const styleSheet = document.createElement('style');
    styleSheet.id = 'ns-chat-voice-styles';
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);
  }

  /**
   * Attach event listeners
   */
  attachEvents() {
    if (!this.voiceBtn) return;

    this.voiceBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.toggleRecording();
    });
  }

  /**
   * Toggle recording state
   */
  async toggleRecording() {
    if (this.isRecording) {
      await this.stopRecording();
    } else {
      await this.startRecording();
    }
  }

  /**
   * Start recording audio
   */
  async startRecording() {
    try {
      // Check if already recording
      if (this.isRecording) return;

      // Request microphone access
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000
        }
      });

      // Create MediaRecorder
      this.mediaRecorder = new MediaRecorder(this.stream);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        this.audioChunks.push(event.data);
      };

      this.mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        await this.transcribeAudio(audioBlob);
        this.cleanupStream();
      };

      this.mediaRecorder.start();
      this.isRecording = true;
      this.updateUIState('recording');
      this.setStatus('Recording... click to stop', 'recording');

    } catch (error) {
      console.error('Voice recording error:', error);
      this.handleError('Microphone access denied. Check your permissions.');
    }
  }

  /**
   * Stop recording
   */
  async stopRecording() {
    if (this.mediaRecorder && this.isRecording) {
      // Wait a moment to ensure audio is captured
      setTimeout(() => {
        this.mediaRecorder.stop();
        this.isRecording = false;
        this.updateUIState('idle');
        this.setStatus('Transcribing...', 'transcribing');
      }, 100);
    }
  }

  /**
   * Transcribe audio using the local server
   */
  async transcribeAudio(audioBlob) {
    try {
      // Convert WebM to WAV for whisper
      const wavBlob = await this.convertToWav(audioBlob);
      
      // Send to transcription server
      const formData = new FormData();
      formData.append('audio', wavBlob, 'recording.wav');

      this.setStatus('Processing...', 'transcribing');

      const response = await fetch(`${this.options.serverUrl}/api/voice-transcribe`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.status === 'ok' && result.text) {
        this.insertTranscript(result.text.trim());
        this.setStatus('Done!', '');
        if (this.options.onTranscribed) {
          this.options.onTranscribed(result.text.trim());
        }
      } else if (result.status === 'empty') {
        this.setStatus('No speech detected', '');
        this.handleError('No speech detected. Try speaking more clearly.');
      } else {
        throw new Error(result.error || 'Transcription failed');
      }

    } catch (error) {
      console.error('Transcription error:', error);
      this.handleError(`Transcription failed: ${error.message}`);
    } finally {
      setTimeout(() => {
        this.setStatus('');
      }, 3000);
    }
  }

  /**
   * Convert WebM blob to WAV format
   */
  async convertToWav(webmBlob) {
    // If it's already WAV, return as-is
    if (webmBlob.type === 'audio/wav') {
      return webmBlob;
    }

    // Use AudioContext to convert
    const arrayBuffer = await webmBlob.arrayBuffer();
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    
    // Convert to mono 16kHz WAV
    const mono = this.toMono(audioBuffer);
    return this.encodeWAV(mono, audioCtx.sampleRate);
  }

  /**
   * Convert to mono
   */
  toMono(audioBuffer) {
    if (audioBuffer.numberOfChannels === 1) {
      return audioBuffer.getChannelData(0);
    }
    const left = audioBuffer.getChannelData(0);
    const right = audioBuffer.getChannelData(1);
    const result = new Float32Array(audioBuffer.length);
    for (let i = 0; i < audioBuffer.length; i++) {
      result[i] = (left[i] + right[i]) / 2;
    }
    return result;
  }

  /**
   * Encode to WAV
   */
  encodeWAV(samples, sampleRate) {
    const length = samples.length * 2 + 44;
    const buffer = new ArrayBuffer(length);
    const view = new DataView(buffer);

    // WAV header
    this.writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    this.writeString(view, 8, 'WAVE');
    this.writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true); // 16-bit
    view.setUint16(34, 16, true);
    this.writeString(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);

    // Convert float to 16-bit PCM
    let offset = 44;
    for (let i = 0; i < samples.length; i++) {
      let s = Math.max(-1, Math.min(1, samples[i]));
      s = s < 0 ? s * 0x8000 : s * 0x7FFF;
      view.setInt16(offset, s, true);
      offset += 2;
    }

    return new Blob([view], { type: 'audio/wav' });
  }

  writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  /**
   * Insert transcript into the chat input
   */
  insertTranscript(text) {
    if (this.inputField) {
      const start = this.inputField.selectionStart || 0;
      const end = this.inputField.selectionEnd || 0;
      const value = this.inputField.value || '';
      
      this.inputField.value = value.substring(0, start) + text + value.substring(end);
      
      // Trigger input event
      const event = new Event('input', { bubbles: true });
      this.inputField.dispatchEvent(event);
      
      // Focus the input
      this.inputField.focus();
    }

    // Dispatch global event for any listeners
    window.dispatchEvent(new CustomEvent('nsVoiceTranscribed', {
      detail: { text, widget: this }
    }));
  }

  /**
   * Update button UI state
   */
  updateUIState(state) {
    if (this.voiceBtn) {
      this.voiceBtn.classList.remove('recording');
      if (state === 'recording') {
        this.voiceBtn.classList.add('recording');
      }
    }
  }

  /**
   * Set status text
   */
  setStatus(text, className = '') {
    if (this.statusIndicator) {
      this.statusIndicator.textContent = text;
      this.statusIndicator.className = 'ns-voice-status-indicator';
      if (className) this.statusIndicator.classList.add(className);
      this.statusIndicator.style.display = text ? 'inline-block' : 'none';
    }
  }

  /**
   * Handle errors
   */
  handleError(message) {
    this.setStatus(message, 'recording');
    if (this.options.onError) {
      this.options.onError(message);
    }
  }

  /**
   * Cleanup microphone stream
   */
  cleanupStream() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
  }

  /**
   * Destroy the widget
   */
  destroy() {
    this.cleanupStream();
    if (this.voiceBtn) this.voiceBtn.remove();
    if (this.statusIndicator) this.statusIndicator.remove();
  }
}

// Export for use
export { ChatVoiceWidget };

// Convenience function for attaching to multiple containers
export function attachVoiceToChats(selectors, options = {}) {
  const widgets = [];
  if (Array.isArray(selectors)) {
    selectors.forEach(sel => {
      const widget = ChatVoiceWidget.attach(sel, options);
      if (widget) widgets.push(widget);
    });
  } else {
    const widget = ChatVoiceWidget.attach(selectors, options);
    if (widget) widgets.push(widget);
  }
  return widgets;
}

// Auto-attach to common chat input selectors
export function initChatVoice(options = {}) {
  const commonSelectors = [
    '.chat-input-container',
    '.message-input-container',
    '.input-area',
    '.chat-form',
    '.message-input-wrapper',
    '[data-chat-input]',
    '.ns-chat-input'
  ];

  return attachVoiceToChats(commonSelectors, options);
}