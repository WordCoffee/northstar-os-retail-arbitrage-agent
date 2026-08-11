#!/usr/bin/env node
import fs from 'fs';
import path from 'path';

const ROOT = process.cwd();

const files = {
  '.gitignore': 'node_modules/\n.env\n.env.local\ncoverage/\ndata/snapshots/*.json\nlogs/\n.DS_Store\n',
  // ... (keep the file map you liked before; the important part is the loop below)
};

for (const [relativePath, content] of Object.entries(files)) {
  const fullPath = path.join(ROOT, relativePath);
  fs.mkdirSync(path.dirname(fullPath), { recursive: true });

  if (fs.existsSync(fullPath)) {
    console.log('skip   ' + relativePath);
    continue;
  }

  fs.writeFileSync(fullPath, content, 'utf8');
    console.log('create ' + relativePath);
}

console.log('\nScaffold complete.');
console.log('Next steps:');
console.log('1. Copy .env.example to .env and fill secrets.');
console.log('2. npm install');
console.log('3. npm run search');
console.log('4. npm run normalize');
console.log('5. npm run score');