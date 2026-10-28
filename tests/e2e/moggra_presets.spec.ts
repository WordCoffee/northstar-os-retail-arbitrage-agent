// Regression: the MOGRA kit and pouch presets must carry the APPROVED values.
//
// Until these landed, `kit-mogra` shipped a placeholder palette and there were no
// Mogra pouch presets at all, so no pouch render could honestly be described as
// dimensionally accurate (BRIEF_pouch_2sku_20261016.md §1 and §2).
//
// Every value asserted here is quoted from the brief verbatim. If a value in the
// brief changes, this test must change with it - and nothing else may be invented.
//
// LOCALHOST ONLY (127.0.0.1:8101), per the AGENTS.md e2e exception.
import { test, expect } from '@playwright/test';

const BRIEF_PALETTE = ['#171717', '#D5A77A', '#9DBA8B', '#F5EEE2', '#9FA9A4', '#253628', '#D0C5AC'];

test('the MOGRA kit carries the approved palette and type', async ({ page }) => {
  await page.goto('http://127.0.0.1:8101/ui/design-studio');
  const kit = await page.evaluate(async () => {
    const m = await import('/ui/src/studio/engine/presets.js');
    return m.DEFAULT_BRAND_KITS.find((k) => k.id === 'kit-mogra') || null;
  });

  expect(kit, 'kit-mogra must exist').not.toBeNull();
  expect(kit.palette).toEqual(BRIEF_PALETTE);
  expect(kit.ink).toBe('#171717');
  expect(kit.paper).toBe('#F5EEE2');
  expect(kit.accent).toBe('#253628');
  expect(kit.headingFont).toBe('Libre Baskerville');
  expect(kit.bodyFont).toBe('DM Sans');
  // The placeholder that shipped before must be gone.
  expect(kit.palette).not.toContain('#4a7a4a');
  expect(kit.palette).not.toContain('#f4f7f0');
});

test('both MOGRA pouch presets exist with the approved millimetre geometry', async ({ page }) => {
  await page.goto('http://127.0.0.1:8101/ui/design-studio');
  const boxes = await page.evaluate(async () => {
    const m = await import('/ui/src/studio/engine/presets.js');
    return m.BOX_PRESETS;
  });

  const lm6 = boxes.find((b) => b.id === 'pouch-mogra-lm6');
  const shi8 = boxes.find((b) => b.id === 'pouch-mogra-shi8');

  expect(lm6, 'pouch-mogra-lm6 must exist').toBeTruthy();
  expect(shi8, 'pouch-mogra-shi8 must exist').toBeTruthy();

  // Exact approved names, sizes and units.
  expect(lm6.name).toBe("Mogra Pouch - Lion's Mane 6oz");
  expect(lm6.size).toEqual([130, 210, 40]);
  expect(lm6.mm).toBe(true);

  expect(shi8.name).toBe('Mogra Pouch - Shiitake 8oz');
  expect(shi8.size).toEqual([150, 210, 40]);
  expect(shi8.mm).toBe(true);

  // A normalised preset must never be mistaken for the real pack.
  const generic = boxes.find((b) => b.id === 'pouch');
  expect(generic.mm).toBeFalsy();
  expect(generic.size).not.toEqual(lm6.size);
});
