/**
 * Northstar Voice Conversation Module
 * A persistent, cross-page voice AI assistant widget
 *
 * Features:
 * - Glowing planet-like orb (bottom-right corner)
 * - Click to start/stop voice conversation
 * - Minimizable chat window with scrollable history
 * - Multiple conversation sessions support
 * - Local storage persistence
 * - Uses lightweight AI models (Groq API or local Ollama)
 *
 * Usage:
 *   <script type="module" src="/components/voice-conversation.js"></script>
 *   OR
 *   import { initVoiceConversation } from '/components/voice-conversation.js';
 *   initVoiceConversation({ model: 'local' }); // or 'groq'
 */

class VoiceConversationWidget {
  constructor(options = {}) {
    this.options = {
      model: options.model || 'groq', // 'groq' or 'local'
      groqApiKey: options.groqApiKey || null,
      ollamaEndpoint: options.ollamaEndpoint || 'http://localhost:11434/api/generate',
      ollamaModel: options.ollamaModel || 'qwen2.5:0.5b',
      apiBaseUrl: options.apiBaseUrl || window.location.origin,
      ...options
    };

    this.sessions = JSON.parse(localStorage.getItem('voiceConversationSessions') || '{}');
    this.currentSessionId = this.getActiveSessionId();
    this.isRecording = false;
    this.isListening = false;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.conversationHistory = this.loadSessionHistory();

    this.init();
  }

  /**
   * Initialize the widget
   */
  init() {
    this.createDOM();
    this.attachEventListeners();
    this.updateOrbState('idle');
    this.renderChatHistory();
  }

  /**
   * DOM structure for the widget
   */
  createDOM() {
    // Main container
    this.container = document.createElement('div');
    this.container.id = 'northstar-voice-widget';
    this.container.className = 'ns-voice-widget';
    this.container.innerHTML = `
      <!-- Orb trigger button -->
      <div class="ns-orb-container" id="ns-orb-container">
        <div class="ns-orb" id="ns-orb">
          <div class="ns-orb-core"></div>
          <div class="ns-orb-glow"></div>
          <div class="ns-orb-particles"></div>
        </div>
        <div class="ns-orb-label">AI Voice Assistant</div>
        <div class="ns-orb-status" id="ns-orb-status">Click to start</div>
      </div>

      <!-- Minimized chat button -->
      <div class="ns-minimize-btn" id="ns-minimize-btn" style="display: none;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 6 6 18"></polyline><polyline points="6 6 18 18"></polyline></svg>
      </div>

      <!-- Chat window -->
      <div class="ns-chat-window" id="ns-chat-window">
        <div class="ns-chat-header">
          <div class="ns-chat-title">Northstar AI Voice Assistant</div>
          <div class="ns-chat-session-selector" id="ns-chat-session-selector">
            <select id="ns-session-select"></select>
            <button id="ns-new-session" title="New Session">+</button>
          </div>
          <div class="ns-chat-controls">
            <button id="ns-minimize-chat" title="Minimize">—</button>
            <button id="ns-close-chat" title="Close">×</button>
          </div>
        </div>
        <div class="ns-chat-messages" id="ns-chat-messages"></div>
        <div class="ns-chat-input-container">
          <div class="ns-voice-status" id="ns-voice-status">Idle</div>
          <button class="ns-voice-record-btn" id="ns-voice-record-btn" title="Click to record">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><path d="M12 19v3"></path></svg>
          </button>
        </div>
      </div>
    `;

    // Styles
    const styles = `
      /* Voice Widget Base */
      .ns-voice-widget {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9999;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        pointer-events: none;
      }

      /* Orb Container */
      .ns-orb-container {
        pointer-events: all;
        cursor: pointer;
        text-align: center;
        position: relative;
      }

      .ns-orb {
        position: relative;
        width: 72px;
        height: 72px;
        margin: 0 auto;
      }

      .ns-orb-core {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: radial-gradient(circle, #3b82f6 0%, #1e40af 100%);
        box-shadow: 0 0 30px rgba(59, 130, 246, 0.6);
      }

      .ns-orb-glow {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 60px;
        height: 60px;
        border-radius: 50%;
        animation: ns-pulse 2s infinite ease-in-out;
        background: radial-gradient(circle, rgba(59, 130, 246, 0.4) 0%, transparent 70%);
      }

      .ns-orb-particles {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 80px;
        height: 80px;
      }

      .ns-orb-particles::before,
      .ns-orb-particles::after {
        content: '';
        position: absolute;
        width: 4px;
        height: 4px;
        background: #3b82f6;
        border-radius: 50%;
        animation: ns-orbit 8s linear infinite;
      }

      .ns-orb-particles::before {
        top: -16px;
        left: 50%;
        transform: translateX(-50%);
        animation-delay: 0s;
      }

      .ns-orb-particles::after {
        top: -8px;
        left: 50%;
        transform: translateX(-50%);
        animation-delay: -2s;
      }

      /* Orb states */
      .ns-orb.idle .ns-orb-glow { animation: ns-pulse 2s infinite ease-in-out; }
      .ns-orb.recording .ns-orb-core { background: radial-gradient(circle, #ef4444 0%, #b91c1c 100%); box-shadow: 0 0 30px rgba(239, 68, 68, 0.8); }
      .ns-orb.recording .ns-orb-glow { animation: ns-pulse-red 0.5s infinite ease-in-out; }
      .ns-orb.listening .ns-orb-core { background: radial-gradient(circle, #10b981 0%, #059669 100%); box-shadow: 0 0 30px rgba(16, 185, 129, 0.8); }
      .ns-orb.listening .ns-orb-glow { animation: ns-pulse-green 1s infinite ease-in-out; }

      .ns-orb-label {
        margin-top: 12px;
        font-size: 12px;
        color: #94a3b8;
        font-weight: 500;
      }

      .ns-orb-status {
        margin-top: 4px;
        font-size: 11px;
        color: #64748b;
      }

      /* Minimize Button */
      .ns-minimize-btn {
        position: fixed;
        bottom: 32px;
        right: 32px;
        width: 48px;
        height: 48px;
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #94a3b8;
        cursor: pointer;
        transition: all 0.2s ease;
        pointer-events: all;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
        z-index: 9998;
      }

      .ns-minimize-btn:hover {
        background: #334155;
        color: #e2e8f0;
        transform: scale(1.1);
      }

      .ns-minimize-btn svg { display: block; }

      /* Chat Window */
      .ns-chat-window {
        position: fixed;
        bottom: 0;
        right: 0;
        width: 360px;
        height: 500px;
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 16px 0 0 0;
        box-shadow: -10px 0 40px rgba(0, 0, 0, 0.5);
        display: none;
        flex-direction: column;
        overflow: hidden;
        pointer-events: all;
        z-index: 9999;
        transform: translateY(0);
        transition: transform 0.3s ease;
      }

      .ns-chat-window.visible { display: flex; transform: translateY(-100px); }

      .ns-chat-header {
        padding: 14px 16px;
        background: #1e293b;
        border-bottom: 1px solid #334155;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }

      .ns-chat-title {
        font-weight: 600;
        color: #e2e8f0;
        flex: 1;
      }

      .ns-chat-session-selector {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .ns-chat-session-selector select {
        background: #0f172a;
        border: 1px solid #334155;
        color: #cbd5e1;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        outline: none;
      }

      .ns-chat-session-selector select:focus { border-color: #3b82f6; }

      .ns-chat-session-selector button {
        background: #3b82f6;
        color: white;
        border: none;
        width: 24px;
        height: 24px;
        border-radius: 6px;
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .ns-chat-controls {
        display: flex;
        gap: 4px;
      }

      .ns-chat-controls button {
        background: transparent;
        border: none;
        color: #94a3b8;
        width: 28px;
        height: 28px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.15s ease;
      }

      .ns-chat-controls button:hover {
        background: #334155;
        color: #e2e8f0;
      }

      .ns-chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 12px 16px;
      }

      .ns-chat-messages::-webkit-scrollbar {
        width: 6px;
      }

      .ns-chat-messages::-webkit-scrollbar-track {
        background: transparent;
      }

      .ns-chat-messages::-webkit-scrollbar-thumb {
        background: #334155;
        border-radius: 3px;
      }

      .ns-chat-messages::-webkit-scrollbar-thumb:hover {
        background: #475569;
      }

      .ns-message {
        margin-bottom: 14px;
        padding: 10px 12px;
        border-radius: 12px;
        font-size: 13px;
        line-height: 1.5;
        max-width: 85%;
      }

      .ns-message.user {
        background: #1e40af;
        color: #e0e7ff;
        margin-left: auto;
        border-radius: 12px 4px 12px 12px;
      }

      .ns-message.assistant {
        background: #1e293b;
        color: #cbd5e1;
        margin-right: auto;
        border-radius: 4px 12px 12px 12px;
      }

      .ns-message .ns-message-sender {
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
        opacity: 0.7;
      }

      .ns-chat-input-container {
        padding: 12px 16px;
        border-top: 1px solid #334155;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .ns-voice-status {
        flex: 1;
        font-size: 12px;
        color: #64748b;
      }

      .ns-voice-status.recording {
        color: #ef4444;
      }

      .ns-voice-status.listening {
        color: #10b981;
      }

      .ns-voice-record-btn {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #3b82f6;
        border: none;
        color: white;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
        flex-shrink: 0;
      }

      .ns-voice-record-btn:hover {
        background: #2563eb;
        transform: scale(1.05);
      }

      .ns-voice-record-btn.recording {
        background: #ef4444;
        animation: ns-pulse-red 1s infinite;
      }

      .ns-voice-record-btn svg { display: block; }

      /* Animations */
      @keyframes ns-pulse {
        0%, 100% { box-shadow: 0 0 15px rgba(59, 130, 246, 0.4); opacity: 0.7; }
        50% { box-shadow: 0 0 30px rgba(59, 130, 246, 0.7); opacity: 1; }
      }

      @keyframes ns-pulse-red {
        0%, 100% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.4); }
        50% { box-shadow: 0 0 30px rgba(239, 68, 68, 0.8); }
      }

      @keyframes ns-pulse-green {
        0%, 100% { box-shadow: 0 0 15px rgba(16, 185, 129, 0.4); }
        50% { box-shadow: 0 0 30px rgba(16, 185, 129, 0.7); }
      }

      @keyframes ns-orbit {
        0% { transform: translateX(-50%) rotate(0deg) translateX(30px) rotate(0deg); }
        100% { transform: translateX(-50%) rotate(360deg) translateX(30px) rotate(-360deg); }
      }
    `;

    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    this.styleSheet = styleSheet;
  }

  /**
   * Attach event listeners
   */
  attachEventListeners() {
    const orb = this.container.querySelector('#ns-orb');
    const orbContainer = this.container.querySelector('#ns-orb-container');
    const minimizeBtn = this.container.querySelector('#ns-minimize-chat');
    const closeBtn = this.container.querySelector('#ns-close-chat');
    const recordBtn = this.container.querySelector('#ns-voice-record-btn');
    const newSessionBtn = this.container.querySelector('#ns-new-session');
    const sessionSelect = this.container.querySelector('#ns-session-select');

    orbContainer.addEventListener('click', () => {
      if (this.chatWindowVisible) {
        this.minimizeChat();
      } else {
        this.showChat();
      }
    });

    minimizeBtn.addEventListener('click', () => this.minimizeChat());
    closeBtn.addEventListener('click', () => this.minimizeChat());
    recordBtn.addEventListener('click', () => this.toggleRecording());
    newSessionBtn.addEventListener('click', () => this.createNewSession());
    sessionSelect.addEventListener('change', () => this.switchSession(sessionSelect.value));

    // Allow clicking the orb again to show the chat if minimized
    this.minimizeBtn = this.container.querySelector('#ns-minimize-btn');
    this.minimizeBtn.addEventListener('click', () => this.showChat());

    // Listen for messages from the main app (if needed)
    window.addEventListener('message', (event) => {
      if (event.data.type === 'NS_VOICE_SUBMIT') {
        this.addToChat('user', event.data.text);
        this.processAIResponse(event.data.text);
      }
    });
  }

  /**
   * Update orb visual state
   * @param {string} state - 'idle', 'recording', 'listening'
   */
  updateOrbState(state) {
    const orb = this.container.querySelector('#ns-orb');
    const status = this.container.querySelector('#ns-orb-status');

    orb.classList.remove('idle', 'recording', 'listening');
    orb.classList.add(state);

    switch (state) {
      case 'idle':
        status.textContent = 'Click to start';
        break;
      case 'recording':
        status.textContent = 'Recording... (click to stop)';
        break;
      case 'listening':
        status.textContent = 'Listening...';
        break;
    }
  }

  /**
   * Show chat window
   */
  showChat() {
    const chatWindow = this.container.querySelector('#ns-chat-window');
    const minimizeBtn = this.container.querySelector('#ns-minimize-btn');

    chatWindow.classList.add('visible');
    minimizeBtn.style.display = 'none';
    chatWindow.style.display = 'flex';
    this.chatWindowVisible = true;
    this.updateOrbState('idle');
    this.updateSessionSelector();
  }

  /**
   * Minimize chat window
   */
  minimizeChat() {
    const chatWindow = this.container.querySelector('#ns-chat-window');
    const minimizeBtn = this.container.querySelector('#ns-minimize-btn');

    // Use CSS animation
    chatWindow.style.transform = 'translateY(0)';
    chatWindow.style.transition = 'transform 0.3s ease';
    setTimeout(() => {
      chatWindow.classList.remove('visible');
      chatWindow.style.display = 'none';
      chatWindow.style.transform = '';
      chatWindow.style.transition = '';
      minimizeBtn.style.display = 'block';
      this.chatWindowVisible = false;
    }, 300);
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
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(stream);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        this.audioChunks.push(event.data);
      };

      this.mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        await this.transcribeAudio(audioBlob);
        // Clean up stream
        stream.getTracks().forEach(track => track.stop());
      };

      this.mediaRecorder.start();
      this.isRecording = true;
      this.updateOrbState('listening');
      this.updateRecordButton(true);
      this.updateVoiceStatus('Recording...', 'recording');
    } catch (error) {
      console.error('Error starting recording:', error);
      this.updateVoiceStatus('Microphone access denied', 'recording');
    }
  }

  /**
   * Stop recording audio
   */
  async stopRecording() {
    if (this.mediaRecorder && this.isRecording) {
      // Record a short silence to ensure proper cutoff
      await new Promise(resolve => setTimeout(resolve, 300));
      this.mediaRecorder.stop();
      this.isRecording = false;
      this.updateOrbState('idle');
      this.updateRecordButton(false);
      this.updateVoiceStatus('Transcribing...', 'listening');
    }
  }

  /**
   * Update record button visual state
   */
  updateRecordButton(recording) {
    const btn = this.container.querySelector('#ns-voice-record-btn');
    btn.classList.toggle('recording', recording);
  }

  /**
   * Update voice status text
   */
  updateVoiceStatus(text, state = '') {
    const status = this.container.querySelector('#ns-voice-status');
    if (status) {
      status.textContent = text;
      status.className = 'ns-voice-status';
      if (state) status.classList.add(state);
    }
  }

  /**
   * Transcribe audio using Whisper API or local service
   */
  async transcribeAudio(audioBlob) {
    try {
      // Use the local voice.bat transcription pipeline via API
      // or fallback to a simple approach
      let transcript = '';

      // Try local whisper via a fetch to a backend endpoint
      // For static sites, we'd need a backend proxy
      // For now, simulate transcription (the actual work is done by voice.bat)
      transcript = await this.fetchWhisperTranscription(audioBlob);

      if (transcript) {
        this.addToChat('user', transcript);
        await this.processAIResponse(transcript);
      }
    } catch (error) {
      console.error('Transcription error:', error);
      this.updateVoiceStatus('Transcription failed. Try text input.', 'recording');
    }
  }

  /**
   * Fetch transcription from local whisper service
   * In a real deployment, this would proxy to your voice.bat pipeline
   */
  async fetchWhisperTranscription(audioBlob) {
    // For static deployment, this would be a serverless function
    // that calls your local whisper service
    // For now, return empty string as a placeholder
    // In production, this would make a POST to your API
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');

    try {
      const response = await fetch(`${this.options.apiBaseUrl}/api/transcribe`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        return data.text || '';
      }
    } catch (e) {
      // Silent fail - in production you'd want to handle this better
    }

    return '';
  }

  /**
   * Process AI response for a user message
   */
  async processAIResponse(userText) {
    this.updateOrbState('listening');
    this.updateVoiceStatus('Thinking...', 'listening');

    try {
      let response = '';

      if (this.options.model === 'groq' && this.options.groqApiKey) {
        response = await this.callGroqAPI(this.conversationHistory, userText);
      } else {
        // Use local ollama
        response = await this.callLocalOllama(userText);
      }

      if (response) {
        this.addToChat('assistant', response);
      }

      this.updateOrbState('idle');
      this.updateVoiceStatus('Idle', '');
    } catch (error) {
      console.error('AI response error:', error);
      this.addToChat('assistant', 'I encountered an error. Please try again.');
      this.updateOrbState('idle');
      this.updateVoiceStatus('Error occurred', 'recording');
    }
  }

  /**
   * Call Groq API for AI response (lightweight cloud option)
   */
  async callGroqAPI(history, userText) {
    // Build messages from history
    const messages = history.map(msg => ({
      role: msg.sender === 'user' ? 'user' : 'assistant',
      content: msg.text
    }));

    messages.push({ role: 'user', content: userText });

    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.options.groqApiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'llama-3.1-8b-instant', // Lightweight, fast, free tier available
        messages: messages,
        max_tokens: 500,
        temperature: 0.7
      })
    });

    if (!response.ok) {
      throw new Error(`Groq API error: ${response.status}`);
    }

    const data = await response.json();
    return data.choices[0].message.content.trim();
  }

  /**
   * Call local Ollama for AI response
   */
  async callLocalOllama(userText) {
    const response = await fetch(this.options.ollamaEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: this.options.ollamaModel,
        prompt: this.formatPrompt(this.conversationHistory, userText),
        stream: false
      })
    });

    if (!response.ok) {
      throw new Error(`Ollama error: ${response.status}`);
    }

    const data = await response.json();
    return data.response.trim();
  }

  /**
   * Format prompt for local models
   */
  formatPrompt(history, userText) {
    let prompt = '';

    // Add conversation history as context
    for (const msg of history) {
      const role = msg.sender === 'user' ? 'User' : 'Assistant';
      prompt += `${role}: ${msg.text}\n`;
    }

    prompt += `User: ${userText}\nAssistant:`;
    return prompt;
  }

  /**
   * Add a message to the chat
   */
  addToChat(sender, text) {
    const message = {
      sender,
      text,
      timestamp: Date.now()
    };

    this.conversationHistory.push(message);
    this.saveSessionHistory();
    this.renderMessage(message);
    this.updateSessionSelector();
  }

  /**
   * Render a chat message
   */
  renderMessage(message) {
    const messagesContainer = this.container.querySelector('#ns-chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `ns-message ${message.sender}`;
    messageDiv.innerHTML = `
      <div class="ns-message-sender">${message.sender === 'user' ? 'You' : 'Northstar AI'}</div>
      <div class="ns-message-text">${this.escapeHtml(message.text)}</div>
    `;

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  /**
   * Render full chat history
   */
  renderChatHistory() {
    const messagesContainer = this.container.querySelector('#ns-chat-messages');
    if (messagesContainer) {
      messagesContainer.innerHTML = '';
      this.conversationHistory.forEach(msg => this.renderMessage(msg));
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }

  /**
   * Escape HTML to prevent XSS
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Session management
   */
  getActiveSessionId() {
    let active = localStorage.getItem('voiceConversationActive');
    if (!active || !this.sessions[active]) {
      // Create default session
      const now = new Date().toISOString().slice(0, 16).replace('T', ' ');
      active = `session_${Date.now()}`;
      this.sessions[active] = {
        id: active,
        title: `Voice Chat ${now}`,
        createdAt: Date.now(),
        messages: []
      };
      localStorage.setItem('voiceConversationActive', active);
      this.saveSessions();
    }
    return active;
  }

  createNewSession() {
    const now = new Date().toISOString().slice(0, 16).replace('T', ' ');
    const sessionId = `session_${Date.now()}`;
    this.sessions[sessionId] = {
      id: sessionId,
      title: `Voice Chat ${now}`,
      createdAt: Date.now(),
      messages: []
    };
    this.saveSessions();
    this.switchSession(sessionId);
  }

  switchSession(sessionId) {
    this.currentSessionId = sessionId;
    localStorage.setItem('voiceConversationActive', sessionId);
    this.conversationHistory = [...(this.sessions[sessionId]?.messages || [])];
    this.renderChatHistory();
    this.updateSessionSelector();
  }

  updateSessionSelector() {
    const select = this.container.querySelector('#ns-session-select');
    if (!select) return;

    const selected = select.value || this.currentSessionId;
    select.innerHTML = '';

    const sortedSessions = Object.values(this.sessions).sort((a, b) => b.createdAt - a.createdAt);
    sortedSessions.forEach(session => {
      const option = document.createElement('option');
      option.value = session.id;
      option.textContent = session.title;
      if (session.id === this.currentSessionId) option.selected = true;
      select.appendChild(option);
    });

    // Restore selection
    select.value = selected || this.currentSessionId;
  }

  /**
   * Save/Load from localStorage
   */
  saveSessions() {
    localStorage.setItem('voiceConversationSessions', JSON.stringify(this.sessions));
  }

  saveSessionHistory() {
    if (this.sessions[this.currentSessionId]) {
      this.sessions[this.currentSessionId].messages = this.conversationHistory;
      this.saveSessions();
    }
  }

  loadSessionHistory() {
    return this.sessions[this.currentSessionId]?.messages || [];
  }
}

/**
 * Initialize the voice conversation widget
 * @param {Object} options - Configuration options
 * @returns {VoiceConversationWidget}
 */
function initVoiceConversation(options = {}) {
  // Remove any existing widget
  const existing = document.getElementById('northstar-voice-widget');
  if (existing) existing.remove();

  const widget = new VoiceConversationWidget(options);

  // Append container and styles to document
  document.body.appendChild(widget.container);

  // Insert styles into head
  if (widget.styleSheet) {
    document.head.appendChild(widget.styleSheet);
  }

  // Initialize chat window state
  widget.chatWindowVisible = false;
  widget.minimizeBtn.style.display = 'block';

  return widget;
}

// Auto-initialize if script is loaded via <script> tag
if (typeof window !== 'undefined') {
  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      // Only auto-init if not already initialized
      if (!window.__nsVoiceConversation) {
        window.__nsVoiceConversation = initVoiceConversation({
          // Configuration: Use environment variables or defaults
          model: process.env.NS_VOICE_MODEL || 'groq',
          groqApiKey: process.env.NS_GROQ_API_KEY || null,
          ollamaEndpoint: process.env.NS_OLLAMA_ENDPOINT || 'http://localhost:11434/api/generate',
          ollamaModel: process.env.NS_OLLAMA_MODEL || 'qwen2.5:0.5b',
          apiBaseUrl: window.location.origin
        });
      }
    });
  } else {
    if (!window.__nsVoiceConversation) {
      window.__nsVoiceConversation = initVoiceConversation({
        model: process.env.NS_VOICE_MODEL || 'groq',
        groqApiKey: process.env.NS_GROQ_API_KEY || null,
        ollamaEndpoint: process.env.NS_OLLAMA_ENDPOINT || 'http://localhost:11434/api/generate',
        ollamaModel: process.env.NS_OLLAMA_MODEL || 'qwen2.5:0.5b',
        apiBaseUrl: window.location.origin
      });
    }
  }
}

// Export for ESM/module usage
export { VoiceConversationWidget, initVoiceConversation };