import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false, // Sequential for local dev server
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1, // Single worker for local dev
  reporter: 'html',
  use: {
    baseURL: 'http://127.0.0.1:8101', // Local dev server only (127.0.0.1 avoids ::1 flakiness)
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'chromium-mobile',
      use: { ...devices['iPhone 12'] },
    },
    // block3-workspaces names its acceptance browsers explicitly, because
    // `chromium-mobile` above is an iPhone 12 descriptor and therefore runs on
    // WEBKIT (Playwright's device list sets defaultBrowserType: 'webkit'), which
    // its name does not say. These two projects say what they run:
    //
    //   desktop-chromium  Desktop Chrome (Chromium)
    //   iphone-12-webkit  iPhone 12 descriptor (WebKit)
    //
    // The workspace click-path specs skip every other project in
    // tests/e2e/workspaces/_runner.ts, so adding these does not double-run the
    // rest of the suite.
    {
      name: 'desktop-chromium',
      testMatch: /workspaces[\\/].*\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'iphone-12-webkit',
      testMatch: /workspaces[\\/].*\.spec\.ts$/,
      use: { ...devices['iPhone 12'] },
    },
  ],
  webServer: {
    command: 'cd northstar-os-ui && npm run dev',
    url: 'http://127.0.0.1:8101',
    reuseExistingServer: true,
    timeout: 120000,
  },
});