import axios from 'axios';
import { config } from '../config.js';

const BASE_URL = 'https://api.brightdata.com/datasets/v3/scrape';
const MAX_RETRIES = 10;
const DEFAULT_RETRY_AFTER = 10000; // 10 seconds default

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function pollForResult(apiKey, datasetId, maxRetries = MAX_RETRIES) {
  const pollUrl = `https://api.brightdata.com/datasets/v3/snapshot?dataset_id=${datasetId}&format=json`;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await axios.get(pollUrl, {
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        timeout: 60000,
        validateStatus: status => status >= 200 && status < 300,
      });

      if (response.status === 200 && response.data) {
        console.log(`Bright Data poll succeeded on attempt ${attempt}`);
        return Array.isArray(response.data) ? response.data : [response.data];
      }
    } catch (error) {
      if (error.response?.status === 404) {
        // Not ready yet, continue polling
      } else if (error.response) {
        throw new Error(`Bright Data poll failed (${error.response.status}): ${JSON.stringify(error.response.data)}`);
      } else {
        console.warn(`Bright Data poll attempt ${attempt} error: ${error.message}`);
      }
    }

    if (attempt < maxRetries) {
      console.log(`Bright Data result not ready, waiting before retry ${attempt + 1}/${maxRetries}...`);
      await sleep(DEFAULT_RETRY_AFTER);
    }
  }

  throw new Error(`Bright Data result not ready after ${maxRetries} polling attempts.`);
}

export async function scrapeDataset(inputs) {
  if (!config.brightData.apiKey) {
    throw new Error('BRIGHTDATA_API_KEY is missing. Check your .env file.');
  }

  const body = { input: inputs };

  try {
    const response = await axios.post(
      `${BASE_URL}?dataset_id=${config.brightData.datasetId}&include_errors=true&format=json`,
      body,
      {
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${config.brightData.apiKey}`,
        },
        timeout: 120000,
        validateStatus: status => status >= 200 && status < 300,
      }
    );

    console.log('Bright Data status:', response.status);
    console.log('Bright Data response preview:', JSON.stringify(response.data).slice(0, 500));

    if (response.status === 202) {
      console.log('Bright Data returned 202 (accepted), polling for result...');
      return pollForResult(config.brightData.apiKey, config.brightData.datasetId);
    }

    if (!response.data) {
      throw new Error('Bright Data returned an empty response body.');
    }

    return Array.isArray(response.data) ? response.data : [response.data];
  } catch (error) {
    if (error.response) {
      throw new Error(`Bright Data request failed (${error.response.status}): ${JSON.stringify(error.response.data)}`);
    }

    throw new Error(`Bright Data request failed: ${error.message}`);
  }
}
