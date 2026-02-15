import { defineConfig, devices } from '@playwright/test';

/**
 * AgentIQ Chat Center — Playwright E2E config.
 *
 * Defaults:
 *   BASE_URL = http://localhost:5173   (Vite dev server)
 *   API_URL  = http://localhost:8001   (FastAPI backend)
 *
 * Override via environment variables:
 *   BASE_URL=https://agentiq.ru/app npx playwright test
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,          // smoke tests run sequentially for clarity
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],
  timeout: 30_000,               // 30s per test
  expect: {
    timeout: 10_000,             // 10s for assertions
  },
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5173',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  /* Do NOT auto-start servers — user should start them manually.
   * See the "How to Run" section in this file's sibling README. */
});
