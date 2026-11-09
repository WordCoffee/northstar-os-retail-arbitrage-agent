// UX-05 — every service route must render its own page, not the Bojo chat shell.
//
// The instrument that found the defect was `python -m tools.vision.ux_audit
// --run` (pixels, 3 of 29 routes rendered). This spec is the UI engineer's
// equivalent and runs on the same localhost dev server: for each service in
// `ty/services.json` (the export of `src/data/serviceRegistry.js`) it visits the
// route and asserts BOTH
//   1. a marker that only that service renders is visible, and
//   2. the chat shell (`mb-shell` / `chat-input`) is not mounted.
//
// A route that redirects to /home fails (2). A route that renders a blank or
// unrelated page fails (1). LOCALHOST ONLY (127.0.0.1:8101) — the narrow e2e
// exception in AGENTS.md; the test itself makes no external request.

import { test, expect, type Page } from '@playwright/test'

// Dev chunk compilation plus one data-gated page (Foundation makes 13 calls)
// can exceed Playwright's 30 s default on a cold run; the marker timeout below
// is deliberately generous and must fit inside this.
test.describe.configure({ timeout: 60000 })

/** 'heading' matches the page's own <h1>; 'testid' matches a unique marker. */
type Marker =
  | { kind: 'heading'; value: string }
  | { kind: 'testid'; value: string }

type ServiceCase = {
  id: string
  /** Route as registered in ty/services.json (may carry a #section). */
  route: string
  /** Pathname the router must be on (hash stripped). */
  path: string
  marker: Marker
  /** Why a role-dependent route can render two honest surfaces. */
  note?: string
}

// Order and routes are the 29 entries of ty/services.json, verbatim.
const SERVICES: ServiceCase[] = [
  { id: 'hub', route: '/hub', path: '/hub', marker: { kind: 'heading', value: 'Operations Hub' } },
  { id: 'ledger', route: '/ledger', path: '/ledger', marker: { kind: 'heading', value: 'The Ledger' } },
  { id: 'prospector', route: '/prospector', path: '/prospector', marker: { kind: 'heading', value: 'Prospector' } },
  { id: 'goldengoose', route: '/goldengoose', path: '/goldengoose', marker: { kind: 'heading', value: 'Golden Goose' } },
  { id: 'offerchisel', route: '/offerchisel', path: '/offerchisel', marker: { kind: 'heading', value: 'OfferChisel' } },
  { id: 'towncrier', route: '/towncrier', path: '/towncrier', marker: { kind: 'heading', value: 'The Town Crier' } },
  { id: 'auctioneer', route: '/auctioneer', path: '/auctioneer', marker: { kind: 'heading', value: 'The Auctioneer' } },
  { id: 'autothink', route: '/autothink', path: '/autothink', marker: { kind: 'heading', value: 'AutothinK' } },
  { id: 'thewatch', route: '/thewatch', path: '/thewatch', marker: { kind: 'heading', value: 'The Watch' } },
  { id: 'rankledger', route: '/rankledger', path: '/rankledger', marker: { kind: 'heading', value: 'RankLedger' } },
  { id: 'rivalboard', route: '/rivalboard', path: '/rivalboard', marker: { kind: 'heading', value: 'The Rival Board' } },
  { id: 'account', route: '/account', path: '/account', marker: { kind: 'heading', value: 'Account Status' } },
  // These three pages own a loading/error/ready surface and only print their
  // heading once the backend answers. The route marker is present in all three
  // states, so a slow backend cannot be mistaken for the chat shell (and a
  // backend that is truly down fails the no-chat-shell assertion, not this one).
  { id: 'foundation', route: '/foundation', path: '/foundation', marker: { kind: 'testid', value: 'foundation-status' } },
  { id: 'jobs', route: '/jobs', path: '/jobs', marker: { kind: 'testid', value: 'jobs-status' } },
  { id: 'keywords', route: '/keywords', path: '/keywords', marker: { kind: 'testid', value: 'keywords-status' } },
  { id: 'beta', route: '/beta', path: '/beta', marker: { kind: 'heading', value: 'NorthstarOS' } },
  // /beta#support is the same document as /beta by design: it is a section of
  // the landing page, registered as its own service. The section renders only
  // for the deep link, which is what makes the route distinguishable.
  { id: 'beta-support', route: '/beta#support', path: '/beta', marker: { kind: 'testid', value: 'beta-support-section' } },
  { id: 'beta-signup', route: '/beta-signup', path: '/beta-signup', marker: { kind: 'heading', value: 'Private Beta Invite' } },
  // Admin-gated. An operator session gets the explicit access-denied surface;
  // a platform admin gets the tester dashboard. Both are this route's own view;
  // neither is the chat shell.
  { id: 'beta-ops', route: '/beta-ops', path: '/beta-ops',
    marker: { kind: 'testid', value: 'route-access-denied' },
    note: 'platform admins render bo-admin-dashboard instead' },
  { id: 'design-studio', route: '/design-studio', path: '/design-studio', marker: { kind: 'heading', value: 'Design Studio' } },
  { id: 'product-finder', route: '/product-finder', path: '/product-finder', marker: { kind: 'heading', value: 'SourceScout' } },
  { id: 'golden-goose', route: '/golden-goose', path: '/golden-goose', marker: { kind: 'heading', value: 'Golden Goose Finder' } },
  { id: 'listings', route: '/listings', path: '/listings', marker: { kind: 'heading', value: 'Listing Guardian' } },
  { id: 'keyword-tracker', route: '/keyword-tracker', path: '/keyword-tracker', marker: { kind: 'heading', value: 'Keyword Tracker' } },
  { id: 'competitor-monitor', route: '/competitor-monitor', path: '/competitor-monitor', marker: { kind: 'heading', value: 'Competitor Monitor' } },
  { id: 'listingforge', route: '/listingforge', path: '/listingforge', marker: { kind: 'heading', value: 'ListingForge' } },
  { id: 'adpilot', route: '/adpilot', path: '/adpilot', marker: { kind: 'heading', value: 'AdPilot' } },
  { id: 'socialpulse', route: '/socialpulse', path: '/socialpulse', marker: { kind: 'heading', value: 'SocialPulse' } },
  { id: 'profitability', route: '/profitability', path: '/profitability', marker: { kind: 'heading', value: 'Profitability Dashboard' } },
]

async function expectNoChatShell(page: Page) {
  // The Bojo shell is the defect: a service route that mounts it is "the same
  // page as home" no matter what its <Route> says.
  await expect(page.getByTestId('mb-shell'), 'the Bojo chat shell mounted on a service route').toHaveCount(0)
  await expect(page.getByTestId('chat-input'), 'the chat composer is present on a service route').toHaveCount(0)
}

for (const service of SERVICES) {
  test(`${service.id} renders its own page (${service.route})`, async ({ page }) => {
    await page.goto(`/ui${service.route}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('main')).toBeVisible({ timeout: 30000 })

    // It must stay on its own path: a bounce to /home is the shell defect in
    // its other form, and it would hide the missing route behind the chat.
    const pathname = new URL(page.url()).pathname
    expect(pathname, `${service.route} redirected away from its own path`).toBe(`/ui${service.path}`)

    await expectNoChatShell(page)

    if (service.id === 'beta-ops') {
      // Role-dependent by design; either honest surface passes, the shell does not.
      const surface = page.locator(
        '[data-testid="route-access-denied"], [data-testid="bo-admin-dashboard"]',
      )
      await expect(surface.first(), `${service.note}`).toBeVisible({ timeout: 45000 })
      return
    }

    if (service.marker.kind === 'heading') {
      await expect(
        page.getByRole('heading', { level: 1, name: service.marker.value, exact: true }),
        `${service.id} did not render its own heading`,
      ).toBeVisible({ timeout: 45000 })
    } else {
      await expect(
        page.getByTestId(service.marker.value),
        `${service.id} did not render its own marker`,
      ).toBeVisible({ timeout: 45000 })
    }
  })
}

test('the chat shell remains the home surface only', async ({ page }) => {
  await page.goto('/ui/home', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mb-shell')).toBeVisible({ timeout: 30000 })
  // The phone lays the shell out differently and does not mount the composer in
  // the frame smoke.spec measures; the desktop frame must still show it.
  if (!test.info().project.name.includes('mobile')) {
    await expect(page.getByTestId('chat-input').first()).toBeVisible({ timeout: 30000 })
  }

  // An unknown path gets the honest NotFound page, not a chat surface that
  // pretends to be the room the user asked for.
  await page.goto('/ui/room-that-does-not-exist', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { level: 1, name: 'Room Not Found' })).toBeVisible({ timeout: 45000 })
  await expectNoChatShell(page)
})
