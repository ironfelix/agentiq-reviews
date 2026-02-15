import { test, expect } from '@playwright/test';
import { loginViaDemoMode, isBackendAvailable } from './helpers/auth';

/**
 * Smoke tests -- verify the app loads, login page renders, and
 * basic navigation works. These should pass even without a backend.
 */

test.describe('Smoke Tests', () => {
  test('app loads at /app/ without JS errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    const response = await page.goto('/app/');
    expect(response?.status()).toBeLessThan(400);

    // Wait for React to render either login or the app shell
    await page.waitForSelector('.login-card, .app-shell', { timeout: 15_000 });

    // Filter out expected errors (e.g. failed API calls when backend is down)
    const unexpectedErrors = consoleErrors.filter(
      (msg) =>
        !msg.includes('ERR_CONNECTION_REFUSED') &&
        !msg.includes('Failed to fetch') &&
        !msg.includes('NetworkError') &&
        !msg.includes('net::ERR_') &&
        !msg.includes('AxiosError'),
    );

    expect(unexpectedErrors).toEqual([]);
  });

  test('login page renders with email and password fields', async ({ page }) => {
    await page.goto('/app/');
    await page.waitForSelector('.login-card', { timeout: 10_000 });

    const emailInput = page.locator('input[type="email"]');
    const passwordInput = page.locator('input[type="password"]');

    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();

    // Check placeholders
    await expect(emailInput).toHaveAttribute('placeholder', 'email@example.com');
    await expect(passwordInput).toHaveAttribute('placeholder', /символов/);
  });

  test('login page has submit button and demo mode button', async ({ page }) => {
    await page.goto('/app/');
    await page.waitForSelector('.login-card', { timeout: 10_000 });

    const submitBtn = page.locator('.btn-primary');
    const demoBtn = page.locator('.btn-secondary');

    await expect(submitBtn).toBeVisible();
    await expect(demoBtn).toBeVisible();
    await expect(demoBtn).toContainText('Демо');
  });

  test('after demo login: sidebar visible and workspace loads', async ({ page }) => {
    await loginViaDemoMode(page);

    // Desktop: sidebar should be visible
    const isMobile = page.viewportSize()?.width && page.viewportSize()!.width < 769;

    if (!isMobile) {
      const sidebar = page.locator('.sidebar');
      await expect(sidebar).toBeVisible();

      // Sidebar items
      await expect(page.locator('.sidebar-label:has-text("Сообщения")')).toBeVisible();
      await expect(page.locator('.sidebar-label:has-text("Аналитика")')).toBeVisible();
    }

    // Chat list or empty state should be present
    const chatCenter = page.locator('.chat-center');
    await expect(chatCenter).toBeVisible({ timeout: 10_000 });
  });

  test('API health endpoint returns 200', async ({ page }) => {
    const backendUp = await isBackendAvailable(page);
    test.skip(!backendUp, 'Backend not available');

    const base = process.env.BASE_URL
      ? `${process.env.BASE_URL}/api`
      : 'http://localhost:8001/api';

    const response = await page.request.get(`${base}/health`);
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('status');
  });

  test('no console errors after login', async ({ page }) => {
    const consoleErrors: string[] = [];

    await loginViaDemoMode(page);

    // Start collecting after login
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Wait a bit for async operations
    await page.waitForTimeout(2_000);

    const unexpectedErrors = consoleErrors.filter(
      (msg) =>
        !msg.includes('ERR_CONNECTION_REFUSED') &&
        !msg.includes('Failed to fetch') &&
        !msg.includes('NetworkError') &&
        !msg.includes('net::ERR_') &&
        !msg.includes('AxiosError') &&
        !msg.includes('401'),
    );

    expect(unexpectedErrors).toEqual([]);
  });
});
