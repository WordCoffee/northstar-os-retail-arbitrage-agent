// a11y — the workspace tab strip (`northstar-os-ui/src/shell/TabBar.jsx`).
//
// The strip is the WAI-ARIA tabs widget: one `role="tablist"`, one `role="tab"`
// per open workspace, and a `role="tabpanel"` page per tab (`ShellLayout.jsx`).
// That pattern has one hard rule this spec exists to enforce: a tablist may own
// ONLY tabs. The close control used to sit inside the tablist, which made
// axe-core report `aria-required-children` (impact: critical) on every page
// that shows two or more open workspaces:
//
//   "Element has children which are not allowed: button[aria-label]"
//   target: .wst-list
//
// LOCALHOST ONLY (127.0.0.1:8101).

import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// The suite rail is a desktop control; the strip itself behaves the same at
// every width, so measure it at a width where two workspaces can be opened.
test.use({ viewport: { width: 1280, height: 900 } })

async function openTwoWorkspaces(page: Page) {
  await page.goto('/ui/listings', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('workspace-tabs')).toBeVisible({ timeout: 30000 })
  await page.locator('aside.suite-rail').getByRole('button', { name: 'SourceScout' }).click()
  await expect(page.getByTestId('workspace-tabs')).toHaveAttribute('data-tab-count', '2')
}

test('the tab strip has no critical or serious axe violations', async ({ page }) => {
  await openTwoWorkspaces(page)
  const results = await new AxeBuilder({ page })
    .include('[data-testid="workspace-tabs"]')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()
  const shape = results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    nodes: v.nodes.length,
    targets: v.nodes.map((n) => String(n.target?.[0] || '')),
    evidence: v.nodes.map((n) => String(n.failureSummary || '').slice(0, 200)),
  }))
  expect(shape, `tab strip a11y violations: ${JSON.stringify(shape, null, 2)}`).toEqual([])
})

test('the tablist owns tabs and nothing else', async ({ page }) => {
  await openTwoWorkspaces(page)

  // Roles and the structure axe checks: every owned child of the tablist is a
  // tab. A presentational wrapper is transparent to the accessibility tree, so
  // this walks exactly the set axe walks.
  const owned = await page.evaluate(() => {
    const list = document.querySelector('[data-testid="workspace-tabs"] [role="tablist"]') as HTMLElement | null
    if (!list) return null
    const collect = (node: Element): string[] => {
      const out: string[] = []
      for (const child of Array.from(node.children)) {
        // The accessibility tree skips aria-hidden subtrees and flattens
        // presentational wrappers — this walk does the same, so it reports what
        // the tablist actually owns.
        if (child.getAttribute('aria-hidden') === 'true') continue
        const role = child.getAttribute('role')
        if (role === 'presentation' || role === 'none') out.push(...collect(child))
        else out.push(role || child.tagName.toLowerCase())
      }
      return out
    }
    const tabs = Array.from(list.querySelectorAll('[role="tab"]'))
    return {
      label: list.getAttribute('aria-label'),
      orientation: list.getAttribute('aria-orientation'),
      describedby: list.getAttribute('aria-describedby'),
      ownedRoles: collect(list),
      tabCount: tabs.length,
      tabs: tabs.map((t) => ({
        id: t.id,
        selected: t.getAttribute('aria-selected'),
        controls: t.getAttribute('aria-controls'),
        tabindex: t.getAttribute('tabindex'),
      })),
      // Whatever exposes the close action must not be reachable inside the
      // tablist: not a button, not focusable, not announced.
      closeAffordances: Array.from(list.querySelectorAll('button')).filter(
        (b) => !b.hasAttribute('role'),
      ).map((b) => ({
        hidden: b.getAttribute('aria-hidden'),
        tabindex: b.getAttribute('tabindex'),
      })),
    }
  })

  expect(owned, 'the tab strip renders a role="tablist"').toBeTruthy()
  expect(owned!.label).toBe('Open workspaces')
  expect(owned!.orientation).toBe('horizontal')
  expect(owned!.tabCount).toBe(2)
  expect(owned!.ownedRoles, 'a tablist may own only tabs').toEqual(['tab', 'tab'])
  for (const tab of owned!.tabs) {
    expect(tab.id, 'every tab is addressable so its panel can be labelled by it').toMatch(/^wst-tab-/)
    expect(tab.controls, 'every tab controls a panel').toMatch(/^wst-panel-/)
    expect(['true', 'false']).toContain(tab.selected)
  }
  // Roving tabindex: exactly one tab is in the Tab order.
  expect(owned!.tabs.filter((t) => t.tabindex === '0')).toHaveLength(1)
  expect(owned!.closeAffordances, 'close controls are present per tab').toHaveLength(2)
  for (const close of owned!.closeAffordances) {
    expect(close.hidden, 'the close affordance is decorative for assistive tech').toBe('true')
    expect(close.tabindex, 'and never a tab stop').toBe('-1')
  }
  // The keyboard close path (Delete) is announced, because the pointer-only
  // affordance is not.
  expect(owned!.describedby, 'the tablist tells AT how to close a tab').toBe('wst-keys-sr')
})

test('the keyboard still switches and closes tabs', async ({ page }) => {
  await openTwoWorkspaces(page)
  const listings = page.getByRole('tab', { name: 'Listing Guardian' })
  const source = page.getByRole('tab', { name: 'SourceScout' })
  await expect(source).toHaveAttribute('aria-selected', 'true')

  await source.focus()
  await page.keyboard.press('ArrowLeft')
  await expect(listings).toHaveAttribute('aria-selected', 'true')
  await expect(listings).toBeFocused()
  await expect(page.locator('#wst-panel-listings')).toBeVisible()

  await page.keyboard.press('ArrowRight')
  await expect(source).toHaveAttribute('aria-selected', 'true')

  // Delete closes the focused tab (the keyboard equivalent of the × affordance).
  await source.focus()
  await page.keyboard.press('Delete')
  await expect(page.getByTestId('workspace-tabs')).toHaveAttribute('data-tab-count', '1')
  await expect(page.getByRole('tab', { name: 'SourceScout' })).toHaveCount(0)
})
