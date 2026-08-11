import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { loadDeals, loadProducts } from '../services/storageService.js';
import { config } from '../config.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();

app.use(cors());
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/deals', (req, res) => {
  res.json(loadDeals());
});

app.get('/api/products', (req, res) => {
  res.json(loadProducts());
});

app.listen(config.server.port, () => {
  console.log(`Dashboard running at http://localhost:${config.server.port}`);
});
