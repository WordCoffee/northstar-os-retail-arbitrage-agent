import fs from 'fs';
import path from 'path';

export async function onRequestGet(context) {
  const { params, env } = context;
  const fileName = params.filename;

  if (!fileName || !fileName.endsWith('.json')) {
    return new Response(JSON.stringify({ error: 'Invalid file name' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const dataDir = path.join(process.cwd(), 'data', 'scored');
  const filePath = path.join(dataDir, fileName);

  // Security: prevent directory traversal
  if (!filePath.startsWith(dataDir) || !fs.existsSync(filePath)) {
    return new Response(JSON.stringify({ error: 'File not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}