import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for AgentIQ Chat Center E2E tests.
 *
 * Run against local dev server:
 *   npx playwright test
 *
 * Run against production:
 *   BASE_URL=https://agentiq.ru npx playwright test
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  timeout: 30_000,

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },

  projects: [
    {
      name: 'desktop',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
    {
      name: 'mobile',
      use: {
        ...devices['iPhone 12'],
        viewport: { width: 390, height: 844 },
      },
    },
  ],

  /* Start local dev server automatically when running locally */
  webServer: process.env.BASE_URL
    ? undefined
    : {
        command: 'npm run dev',
        url: 'http://localhost:5173/app/',
        reuseExistingServer: !process.env.CI,
        timeout: 30_000,
      },
});
