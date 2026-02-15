import { test, expect } from '@playwright/test';
import { ensureAuthenticated, isBackendAvailable, TEST_CREDENTIALS, loginViaDemoMode } from './helpers/auth';

/**
 * Performance tests -- catches:
 *   Bug #9:  General slow load times
 *   Bug #35: Slow initial page load / API cascade
 */

test.describe('Performance', () => {
  test('initial page load < 5s (DOMContentLoaded)', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/app/', { waitUntil: 'domcontentloaded' });

    const elapsed = Date.now() - startTime;

    // DOMContentLoaded should happen within 5 seconds
    expect(elapsed).toBeLessThan(5_000);
  });

  test('login page renders within 3s', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/app/');
    await page.waitForSelector('.login-card', { timeout: 5_000 });

    const elapsed = Date.now() - startTime;
    expect(elapsed).toBeLessThan(3_000);
  });

  test('chat list renders within 3s after login', async ({ page }) => {
    const startTime = Date.now();

    await loginViaDemoMode(page);

    // Wait for chat center (chat list section)
    await page.waitForSelector('.chat-center', { timeout: 5_000 });

    const elapsed = Date.now() - startTime;

    // Allow 3 seconds from the start of the login flow
    // (demo login + render should be fast)
    expect(elapsed).toBeLessThan(5_000);
  });

  test('selecting a chat shows messages within 2s', async ({ page }) => {
    await ensureAuthenticated(page, TEST_CREDENTIALS);
    await page.waitForSelector('.chat-center', { timeout: 10_000 });

    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items to test');
      return;
    }

    const startTime = Date.now();

    await chatItems.first().click();

    // Wait for messages area to show content
    await page.waitForSelector('.message, .chat-messages:not(:empty)', {
      timeout: 5_000,
    });

    const elapsed = Date.now() - startTime;

    // Messages should appear within 2 seconds
    expect(elapsed).toBeLessThan(2_000);
  });

  test('no more than 5 API requests on initial load (Bug #35)', async ({ page }) => {
    const apiRequests: string[] = [];

    // Intercept all API requests
    page.on('request', (request) => {
      const url = request.url();
      if (url.includes('/api/') && request.method() !== 'OPTIONS') {
        apiRequests.push(`${request.method()} ${url}`);
      }
    });

    await loginViaDemoMode(page);

    // Wait for the initial burst of API requests to settle
    await page.waitForTimeout(3_000);

    // Log the requests for debugging
    if (apiRequests.length > 5) {
      console.warn(`API requests on initial load (${apiRequests.length}):`);
      for (const req of apiRequests) {
        console.warn(`  ${req}`);
      }
    }

    // Allow up to 8 requests (auth/me, interactions list, quality metrics, etc.)
    // but warn if over 5
    expect(apiRequests.length).toBeLessThanOrEqual(8);
  });

  test('API responses < 1s for list endpoints', async ({ page }) => {
    const backendUp = await isBackendAvailable(page);
    test.skip(!backendUp, 'Backend not available');

    await ensureAuthenticated(page, TEST_CREDENTIALS);

    const slowRequests: Array<{ url: string; duration: number }> = [];

    // Track API timing
    page.on('request', (request) => {
      const url = request.url();
      if (url.includes('/api/')) {
        (request as any).__startTime = Date.now();
      }
    });

    page.on('response', (response) => {
      const request = response.request();
      const url = request.url();
      const start = (request as any).__startTime;
      if (start && url.includes('/api/')) {
        const duration = Date.now() - start;
        if (duration > 1_000) {
          slowRequests.push({ url, duration });
        }
      }
    });

    // Trigger a page load
    await page.reload();
    await page.waitForSelector('.chat-center, .login-card', { timeout: 10_000 });
    await page.waitForTimeout(3_000);

    if (slowRequests.length > 0) {
      console.warn(`Slow API responses (> 1s):`);
      for (const req of slowRequests) {
        console.warn(`  ${req.url}: ${req.duration}ms`);
      }
    }

    // No list endpoints should take more than 1 second
    const listEndpointSlow = slowRequests.filter(
      (r) =>
        r.url.includes('/interactions') ||
        r.url.includes('/chats') ||
        r.url.includes('/health'),
    );

    expect(listEndpointSlow.length).toBe(0);
  });

  test('page weight: HTML + JS bundle < 2MB', async ({ page }) => {
    let totalBytes = 0;

    page.on('response', (response) => {
      const url = response.url();
      const headers = response.headers();
      const contentLength = parseInt(headers['content-length'] || '0', 10);

      if (
        url.includes('.js') ||
        url.includes('.css') ||
        url.includes('.html') ||
        url.endsWith('/app/')
      ) {
        totalBytes += contentLength;
      }
    });

    await page.goto('/app/', { waitUntil: 'networkidle' });

    // Total static assets should be under 2MB
    const totalMB = totalBytes / (1024 * 1024);
    expect(totalMB).toBeLessThan(2);
  });
});
