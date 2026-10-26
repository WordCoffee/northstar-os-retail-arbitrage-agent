import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false, // Sequential for local dev server
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1, // Single worker for local dev
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:8101', // Local dev server only
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
  ],
  webServer: {
    command: 'cd northstar-os-ui && npm run dev',
    url: 'http://localhost:8101',
    reuseExistingServer: true,
    timeout: 120000,
  },
});