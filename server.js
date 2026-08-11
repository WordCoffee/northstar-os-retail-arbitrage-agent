import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { loadLatestDeals, findLatestScoredJson, findLatestTopDealsCsv, countScoredRuns } from './src/lib/dealsApi.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, 'public');
const SCORED_DIR = path.join(__dirname, 'data/scored');
const PORT = process.env.PORT || 8788;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.csv': 'text/csv; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

function sendJson(res, obj, status = 200) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=60' });
  res.end(JSON.stringify(obj));
}

function sendFile(res, filePath) {
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Server error');
      return;
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(filePath)] || 'application/octet-stream' });
    res.end(data);
  });
}

function safeFilename(name) {
  return /^[a-zA-Z0-9][a-zA-Z0-9._-]*\.json$/.test(name) ? name : null;
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = decodeURIComponent(url.pathname);

  if (pathname === '/api/latest-deals' && req.method === 'GET') {
    return sendJson(res, loadLatestDeals());
  }

  if (pathname === '/api/files' && req.method === 'GET') {
    if (!fs.existsSync(SCORED_DIR)) return sendJson(res, { files: [] });
    const files = fs.readdirSync(SCORED_DIR)
      .filter(f => f.startsWith('scored-') && f.endsWith('.json'))
      .map(f => ({ name: f, mtime: fs.statSync(path.join(SCORED_DIR, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);
    return sendJson(res, { files, runCount: countScoredRuns() });
  }

  if (pathname.startsWith('/api/data/') && req.method === 'GET') {
    const name = pathname.slice('/api/data/'.length);
    if (!safeFilename(name)) return sendJson(res, { error: 'Bad filename' }, 400);
    const filePath = path.join(SCORED_DIR, name);
    if (!fs.existsSync(filePath)) return sendJson(res, { error: 'Not found' }, 404);
    return sendFile(res, filePath);
  }

  const rel = pathname === '/' ? 'index.html' : pathname;
  const filePath = path.join(PUBLIC_DIR, rel);
  if (filePath.startsWith(PUBLIC_DIR) && fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    return sendFile(res, filePath);
  }

  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end('Not found');
});

server.listen(PORT, () => {
  console.log(`Northstar OS dashboard running at http://localhost:${PORT}`);
  console.log(`API: http://localhost:${PORT}/api/latest-deals`);
});
