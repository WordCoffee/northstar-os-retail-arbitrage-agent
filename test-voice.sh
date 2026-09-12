#!/bin/bash
# Quick test script for the voice conversation module
# Run: chmod +x test-voice.sh && ./test-voice.sh

cd "$(dirname "$0")"

echo "=== Voice Conversation Widget Test ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check for Python (for simple HTTP server)
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "  [FAIL] Python not found"
else
    echo "  [OK] Python found"
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "  [FAIL] Node.js not found"
else
    echo "  [OK] Node.js found ($(node --version))"
fi

# Check sox
if ! command -v sox &> /dev/null; then
    echo "  [FAIL] sox not found"
else
    echo "  [OK] sox found"
fi

# Check whisper-cli
if ! command -v whisper-cli &> /dev/null; then
    echo "  [FAIL] whisper-cli not found"
else
    echo "  [OK] whisper-cli found"
fi

# Check Ollama
if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "  [OK] Ollama running"
else
    echo "  [WARN] Ollama not running (start with: ollama serve)"
fi

echo ""
echo "=== Starting test server ==="
echo "Opening http://localhost:8000/voice-test.html in browser..."
echo "Press Ctrl+C to stop"
echo ""

# Use Python's built-in HTTP server
if command -v python3 &> /dev/null; then
    python3 -m http.server 8000
elif command -v python &> /dev/null; then
    python -m http.server 8000
else
    echo "No Python available - run your own HTTP server on port 8000"
    echo "Then open: http://localhost:8000/voice-test.html"
fi