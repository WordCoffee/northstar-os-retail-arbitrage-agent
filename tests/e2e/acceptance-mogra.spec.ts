// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// MOGRA acceptance through the REAL CHAT BOX (T3 / T5)
//
// Every assertion below comes from the browser: the operator types into the
// NorthstarOS chat composer ([data-testid="chat-input"]), presses Send, the turn
// streams over the app's own SSE endpoint, the tool runs, and the artifact is
// rendered in the chat as a real <img>. The image's naturalWidth/naturalHeight
// is the delivered pixel size â€” not a backend claim.
//
// Scope: LOCALHOST ONLY (127.0.0.1:8101), as permitted by AGENTS.md for
// tests/e2e. No external host, no Amazon, no provider key.
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const SHOTS = path.resolve('reports/acceptance_restart_20261027');
fs.mkdirSync(SHOTS, { recursive: true });

test.use({ acceptDownloads: true });
test.describe.configure({ mode: 'serial' });

async function openStudio(page) {
  await page.goto('http://127.0.0.1:8101/ui/design-studio');
  await expect(page.getByTestId('chat-input')).toBeVisible({ timeout: 45000 });
  // The dev-only identity banner proves which posture we are testing under.
  await expect(page.getByText('DEV: AUTH DISABLED')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('Authentication required');
}

async function send(page, text) {
  const input = page.getByTestId('chat-input');
  await input.click();
  await input.fill(text);
  await page.getByTestId('chat-send').click();
}

/** Start a clean session and pin the composer to fast, non-thinking turns. */
async function newSessionFast(page) {
  await page.getByTestId('chat-new').click();
  await page.getByTestId('chat-options-toggle').click();
  await page.getByTestId('chat-mode').selectOption('creative');
  await page.getByTestId('chat-thinking').selectOption('off');
  await page.getByTestId('chat-style').selectOption('concise');
  await page.getByTestId('chat-options-toggle').click();
}

/** Wait for the assistant to finish the turn (tool summary or an honest error). */
async function awaitTurn(page, pattern, timeout = 480000) {
  await expect(page.locator('.chat-col')).toContainText(pattern, { timeout });
}
test('T-auth: the authenticated workspace loads with the chat box', async ({ page }) => {
  await openStudio(page);
  await expect(page.getByText('Engine: bojo')).toBeVisible();
  await newSessionFast(page);
  await page.screenshot({ path: path.join(SHOTS, 'T-auth-workspace.png'), fullPage: false });
});

test('T3: 2000x2000 Amazon MAIN render requested from the chat box', async ({ page }) => {
  test.setTimeout(600000);
  await openStudio(page);
  await newSessionFast(page);
  await send(page,
    'Generate the Amazon MAIN listing image now by calling generate_image with width 2000 and height 2000. ' +
    'Subject: Mogra Organics Organic Lion\'s Mane Mushroom Powder, a 6 oz kraft stand-up pouch, ' +
    'the bare pouch centred on a pure white seamless studio background, soft even light, no props, ' +
    'no text or logos on the pouch.');
  await page.screenshot({ path: path.join(SHOTS, 'T3-sent.png') });

  // The tool summary is written by chat_tools from the engine's real result.
  //
  // Match the SUMMARY, not a bare "2000 x 2000": the model's own reasoning text
  // ("I need to use generate_image with width: 2000 ... height: 2000") also
  // contains those numbers, so the loose pattern let the assertion run while the
  // turn was still generating and the artefact did not exist yet.
  await awaitTurn(page, /Rendered a 2000x2000 image/);

  // The artifact must be VISIBLE in the chat, and its decoded size is the proof.
  const img = page.locator('.chat-col img[alt]').last();
  await expect(img).toBeVisible({ timeout: 60000 });
  await expect.poll(async () => img.evaluate((el) => el.complete && el.naturalWidth > 0),
    { timeout: 60000 }).toBe(true);
  const size = await img.evaluate((el) => ({ w: el.naturalWidth, h: el.naturalHeight }));
  expect(size).toEqual({ w: 2000, h: 2000 });

  const transcript = await page.locator('.chat-col').innerText();
  fs.writeFileSync(path.join(SHOTS, 'T3-transcript.txt'), transcript, 'utf8');
  await page.screenshot({ path: path.join(SHOTS, 'T3-rendered-2000.png'), fullPage: true });

  // Download through the UI control, then prove the saved file is a 2000x2000 PNG.
  const dl = page.waitForEvent('download', { timeout: 60000 });
  await page.locator('.chat-col').getByRole('button', { name: /download/i }).last().click();
  const download = await dl;
  const saved = path.join(SHOTS, 'T3-downloaded.png');
  await download.saveAs(saved);
  const head = fs.readFileSync(saved).subarray(0, 24);
  expect(head.subarray(1, 4).toString('ascii')).toBe('PNG');
  const w = head.readUInt32BE(16), h = head.readUInt32BE(20);
  expect({ w, h }).toEqual({ w: 2000, h: 2000 });

  // Refresh persistence: reload and the same artifact must come back from the store.
  await page.reload();
  await expect(page.getByTestId('chat-input')).toBeVisible({ timeout: 45000 });
  await expect(page.locator('.chat-col')).toContainText(/2000\s*[xÃ—]\s*2000/, { timeout: 60000 });
  const img2 = page.locator('.chat-col img[alt]').last();
  await expect.poll(async () => img2.evaluate((el) => el.complete && el.naturalWidth > 0),
    { timeout: 60000 }).toBe(true);
  expect(await img2.evaluate((el) => ({ w: el.naturalWidth, h: el.naturalHeight })))
    .toEqual({ w: 2000, h: 2000 });
  await page.screenshot({ path: path.join(SHOTS, 'T3-after-refresh.png'), fullPage: true });
});

test('T5: 1464x600 A+ Premium banner requested from the chat box', async ({ page }) => {
  test.setTimeout(600000);
  await openStudio(page);
  await newSessionFast(page);
  await send(page,
    'Generate the Amazon A+ Premium full-width banner now by calling generate_image with width 1464 and height 600. ' +
    'Subject: Mogra Organics Organic Lion\'s Mane Mushroom Powder 6 oz pouch on a warm linen surface ' +
    'with dried lion\'s mane and a ceramic bowl, soft daylight, generous empty space on the right, ' +
    'no text or logos.');
  await page.screenshot({ path: path.join(SHOTS, 'T5-sent.png') });

  await awaitTurn(page, /Rendered a 1464x600 image/);

  const img = page.locator('.chat-col img[alt]').last();
  await expect(img).toBeVisible({ timeout: 60000 });
  await expect.poll(async () => img.evaluate((el) => el.complete && el.naturalWidth > 0),
    { timeout: 60000 }).toBe(true);
  expect(await img.evaluate((el) => ({ w: el.naturalWidth, h: el.naturalHeight })))
    .toEqual({ w: 1464, h: 600 });

  fs.writeFileSync(path.join(SHOTS, 'T5-transcript.txt'),
    await page.locator('.chat-col').innerText(), 'utf8');
  await page.screenshot({ path: path.join(SHOTS, 'T5-rendered-1464x600.png'), fullPage: true });
});



