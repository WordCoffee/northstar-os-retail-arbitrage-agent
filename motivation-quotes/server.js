import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { getRandomQuote, getQuotesByCategory, getCategories, quotes } from './quotes.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/quote', (req, res) => {
  const quote = getRandomQuote();
  res.json(quote);
});

app.get('/api/quotes', (req, res) => {
  const { category, limit } = req.query;
  
  let result = quotes;
  
  if (category) {
    result = getQuotesByCategory(category);
  }
  
  if (limit) {
    result = result.slice(0, parseInt(limit));
  }
  
  res.json(result);
});

app.get('/api/categories', (req, res) => {
  res.json(getCategories());
});

app.get('/api/quote/:category', (req, res) => {
  const { category } = req.params;
  const categoryQuotes = getQuotesByCategory(category);
  
  if (categoryQuotes.length === 0) {
    return res.status(404).json({ error: 'Category not found' });
  }
  
  const quote = categoryQuotes[Math.floor(Math.random() * categoryQuotes.length)];
  res.json(quote);
});

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/journal', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'journal.html'));
});

app.get('/daily', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'daily.html'));
});

app.get('/mood', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'mood.html'));
});

app.get('/games', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'games.html'));
});

app.listen(PORT, () => {
  console.log(`\n  Daily Dose — Motivation Quote Generator\n  http://localhost:${PORT}\n\n  Pages:\n    Home:    http://localhost:${PORT}/\n    Journal: http://localhost:${PORT}/journal.html\n    Daily:   http://localhost:${PORT}/daily.html\n    Mood:    http://localhost:${PORT}/mood.html\n    Games:   http://localhost:${PORT}/games.html\n`);
});