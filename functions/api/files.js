import fs from 'fs';
import path from 'path';

export async function onRequestGet(context) {
  const { env } = context;
  const dataDir = path.join(process.cwd(), 'data', 'scored');

  if (!fs.existsSync(dataDir)) {
    return new Response(JSON.stringify([]), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const files = fs.readdirSync(dataDir)
      .filter(f => f.endsWith('.json') && f.startsWith('scored-'))
      .map(f => {
        const fullPath = path.join(dataDir, f);
        const stat = fs.statSync(fullPath);
        const data = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
        return {
          name: f,
          sizeKB: Math.round(stat.size / 1024),
          rows: data.meta?.rowCount || 0,
          qualified: data.meta?.qualifiedCount || 0,
          modified: stat.mtime
        };
      })
      .sort((a, b) => new Date(b.modified) - new Date(a.modified));

    return new Response(JSON.stringify(files), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}