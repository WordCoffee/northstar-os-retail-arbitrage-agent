// ═══════════════════════════════════════════════════════════════════════════
// REGRESSION: the chat composer must stay geometrically stable.
//
// Defect found 2026-10-28 during the MOGRA T1 acceptance run. A transcript that
// sits near the overflow threshold oscillated: the scrollbar appeared, the
// content box narrowed, a width-scaled artefact image got shorter, the content
// stopped overflowing, the scrollbar disappeared — forever. The panel visibly
// jittered and Playwright's "stable" actionability check never settled, so the
// composer could not be clicked and the whole Design Studio workflow was
// unrunnable through Chrome Connect (six consecutive `action_error` timeouts at
// uiScale=100, with the element visible, enabled and topmost).
//
// The fix reserves the scrollbar gutter (`scrollbar-gutter: stable`) so the
// presence of a scrollbar can never change layout. This test pins both halves:
// the computed style AND the observable geometry.
//
// Scope: LOCALHOST ONLY (127.0.0.1:8101), per the AGENTS.md e2e exception.
//
// Route corrected 2026-11-11: this spec used to wait for `chat-input` on
// /ui/design-studio, which renders no chat surface at all — the composer lives in
// CreativeStudio (northstar-os-ui/src/pages/internal/CreativeStudio.jsx:733 renders
// <CreativeChat /> in the Northstar shell), and CreativeChat mounts ChatSurface,
// which owns `data-testid="chat-input"`. A spec that waits for an element the page
// cannot render tests a product that does not exist; it is now pointed at the room
// the composer is actually in and pins the route so it cannot drift back.
// ═══════════════════════════════════════════════════════════════════════════

import { test, expect } from '@playwright/test';

test('the chat composer holds a stable box across frames', async ({ page }) => {
  test.setTimeout(120000);

  await page.goto('http://127.0.0.1:8101/ui/creative-studio');
  await page.getByTestId('chat-input').waitFor({ state: 'attached', timeout: 45000 });
  await page.waitForTimeout(2000);
  expect(new URL(page.url()).pathname, 'the composer must be tested where it renders')
    .toBe('/ui/creative-studio');

  // The gutter must be reserved on both shells, otherwise the oscillation
  // described above comes straight back.
  const gutters = await page.evaluate(() => {
    const read = (sel: string) => {
      const el = document.querySelector(sel) as HTMLElement | null;
      if (!el) return null;
      return getComputedStyle(el).scrollbarGutter;
    };
    return {
      stream: read('[data-testid="chat-stream"]'),
      composer: read('textarea[data-testid="chat-input"]'),
    };
  });
  expect(gutters.stream, 'the chat stream must reserve its scrollbar gutter').toBe('stable');

  // And the observable consequence: the composer must not move frame to frame.
  const boxes = await page.evaluate(async () => {
    const out: number[][] = [];
    for (let i = 0; i < 20; i += 1) {
      const el = document.querySelector('textarea[data-testid="chat-input"]') as HTMLElement;
      const r = el.getBoundingClientRect();
      out.push([r.x, r.y, r.width, r.height].map((n) => Math.round(n * 100) / 100));
      await new Promise((res) => requestAnimationFrame(() => res(null)));
    }
    return out;
  });

  const distinct = new Set(boxes.map((b) => b.join(',')));
  expect([...distinct], 'the composer box changed between animation frames').toHaveLength(1);
});
