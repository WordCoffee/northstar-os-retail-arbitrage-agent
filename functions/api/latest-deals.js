import { loadLatestDeals } from '../../../src/lib/dealsApi.js';

export async function onRequestGet() {
  try {
    const data = loadLatestDeals();
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=60' },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}