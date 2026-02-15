import { type Page } from '@playwright/test';

/**
 * Auth helper for E2E tests.
 *
 * The frontend stores the JWT in localStorage under `auth_token`.
 * For tests that need an authenticated session, we either:
 *   1. Log in via API and inject the token into localStorage (fast path), or
 *   2. Use the Demo Mode button when no real backend is available.
 */

const TOKEN_STORAGE_KEY = 'auth_token';

interface LoginCredentials {
  email: string;
  password: string;
}

/**
 * Log in via the backend /api/auth/login endpoint and inject the
 * returned token into the page's localStorage.
 *
 * The page must have already navigated to the app origin so that
 * localStorage is scoped correctly.
 */
export async function loginViaAPI(
  page: Page,
  credentials: LoginCredentials,
  apiBaseURL?: string,
): Promise<string> {
  const base = apiBaseURL || (process.env.BASE_URL ? `${process.env.BASE_URL}/api` : 'http://localhost:8001/api');

  const response = await page.request.post(`${base}/auth/login`, {
    data: {
      email: credentials.email,
      password: credentials.password,
    },
  });

  if (!response.ok()) {
    throw new Error(`Login failed with status ${response.status()}: ${await response.text()}`);
  }

  const body = await response.json();
  const token: string = body.access_token;

  // Navigate to app origin first (localStorage is origin-scoped)
  await page.goto('/app/');

  // Inject token
  await page.evaluate(
    ({ key, value }) => {
      localStorage.setItem(key, value);
    },
    { key: TOKEN_STORAGE_KEY, value: token },
  );

  // Reload so the app picks up the token
  await page.reload();

  return token;
}

/**
 * Log in via the Demo Mode button on the login page.
 * This works even when the backend is unavailable.
 */
export async function loginViaDemoMode(page: Page): Promise<void> {
  await page.goto('/app/');
  // Wait for login page to render
  await page.waitForSelector('.login-card', { timeout: 10_000 });
  // Click the demo mode button
  await page.click('.btn-secondary');
  // Wait for the app shell to appear (sidebar or bottom-nav)
  await page.waitForSelector('.app-shell', { timeout: 10_000 });
}

/**
 * Check if a backend is reachable.
 */
export async function isBackendAvailable(page: Page): Promise<boolean> {
  try {
    const base = process.env.BASE_URL
      ? `${process.env.BASE_URL}/api`
      : 'http://localhost:8001/api';

    const response = await page.request.get(`${base}/health`, { timeout: 5_000 });
    return response.ok();
  } catch {
    return false;
  }
}

/**
 * Ensure the page is authenticated. Tries API login first, falls back to demo mode.
 */
export async function ensureAuthenticated(
  page: Page,
  credentials?: LoginCredentials,
): Promise<void> {
  const backendUp = await isBackendAvailable(page);

  if (backendUp && credentials) {
    await loginViaAPI(page, credentials);
  } else {
    await loginViaDemoMode(page);
  }
}

/** Default test credentials (for local dev / demo) */
export const TEST_CREDENTIALS: LoginCredentials = {
  email: 'test@agentiq.ru',
  password: 'testpass123',
};
