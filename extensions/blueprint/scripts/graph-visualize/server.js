/**
 * Simple static file server for the glossary graph visualization.
 * Usage: node server.js [port]
 *   defaults to port 3000
 */

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = parseInt(process.argv[2]) || 3000;
const STATIC_DIR = __dirname;

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

async function serveStatic(req, res) {
  // Strip query string for file path resolution
  const cleanUrl = req.url.split('?')[0];
  const relativePath = cleanUrl === '/' ? '/index.html' : cleanUrl;
  const filePath = join(STATIC_DIR, relativePath);

  // Prevent directory traversal
  if (!filePath.startsWith(STATIC_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  try {
    const data = await readFile(filePath);
    const ext = extname(filePath);
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(data);
  } catch (err) {
    if (err.code === 'ENOENT') {
      // Fallback to index.html for SPA routing
      try {
        const data = await readFile(join(STATIC_DIR, 'index.html'));
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(data);
      } catch {
        res.writeHead(500);
        res.end('Server error');
      }
    } else {
      res.writeHead(500);
      res.end('Server error');
    }
  }
}

const server = createServer(serveStatic);
server.listen(PORT, () => {
  console.log(`Glossary Graph running at http://localhost:${PORT}`);
});
