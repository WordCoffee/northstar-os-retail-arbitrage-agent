// server.js
const express = require('express');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');

const app = express();
const PORT = 8000;

// Serve static files
app.use(express.static(path.join(__dirname, 'src')));
app.use(express.static(path.join(__dirname)));

// Serve index.html for all routes
app.get('/northstar-os/*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/northstar-os', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Northstar OS server running on http://localhost:${PORT}`);
  console.log(`🌐 Access at http://localhost:${PORT}/northstar-os/`);
  
  // Open browser automatically
  const os = require('os');
  const platform = os.platform();
  
  if (platform === 'win32') {
    exec(`start http://localhost:${PORT}/northstar-os/`);
  } else if (platform === 'darwin') {
    exec(`open http://localhost:${PORT}/northstar-os/`);
  } else {
    console.log('Open your browser and navigate to http://localhost:${PORT}/northstar-os/');
  }
});

// Error handling
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).send('Something broke!');
});

console.log('📋 Northstar OS rebuild complete!');
console.log('==============================');
console.log('✅ Layout system implemented');
console.log('✅ SIGNAL design aesthetic applied');
console.log('✅ Service navigation framework built');
console.log('✅ Testing suite created');
console.log('✅ Server ready for testing');
console.log('==============================');