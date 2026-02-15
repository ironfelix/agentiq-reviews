import { type Page, expect } from '@playwright/test';

/**
 * Generate a unique test email for each test run to avoid conflicts.
 * Format: e2e-<timestamp>-<random>@test.agentiq.local
 */
export function generateTestEmail(): string {
  const ts = Date.now();
  const rand = Math.random().toString(36).slice(2, 8);
  return `e2e-${ts}-${rand}@test.agentiq.local`;
}

/** Default test password (>= 8 chars as required by the form). */
export const TEST_PASSWORD = 'TestPass123!';

/** Default test company name. */
export const TEST_COMPANY = 'E2E Smoke Test Co';

/**
 * Register a new user via the Login page.
 * After successful registration the page should redirect to onboarding.
 */
export async function registerUser(
  page: Page,
  options?: { email?: string; password?: string; name?: string },
): Promise<{ email: string; password: string; name: string }> {
  const email = options?.email ?? generateTestEmail();
  const password = options?.password ?? TEST_PASSWORD;
  const name = options?.name ?? TEST_COMPANY;

  // Navigate to root — the app shows <Login> when not authenticated
  await page.goto('/');

  // Switch to registration mode
  const switchBtn = page.getByRole('button', { name: /Нет аккаунта\? Зарегистрироваться/i });
  await switchBtn.click();

  // Fill in the registration form
  await page.locator('#name').fill(name);
  await page.locator('#email').fill(email);
  await page.locator('#password').fill(password);

  // Submit
  await page.getByRole('button', { name: /Зарегистрироваться/i }).click();

  // Wait for either onboarding or main app to load (redirect from Login)
  await expect(
    page.locator('.onboarding, .app-shell, .demo-banner').first(),
  ).toBeVisible({ timeout: 15_000 });

  return { email, password, name };
}

/**
 * Login with existing credentials.
 * After successful login the page should redirect to onboarding or inbox.
 */
export async function loginUser(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto('/');

  // Make sure we are on the login form (not register)
  const loginHeader = page.locator('.login-header');
  await expect(loginHeader).toBeVisible({ timeout: 10_000 });

  // If the form is in "register" mode, switch to login
  const switchToLogin = page.getByRole('button', { name: /Уже есть аккаунт\? Войти/i });
  if (await switchToLogin.isVisible().catch(() => false)) {
    await switchToLogin.click();
  }

  await page.locator('#email').fill(email);
  await page.locator('#password').fill(password);
  await page.getByRole('button', { name: /^Войти$/i }).click();

  // Wait for redirect away from Login page
  await expect(
    page.locator('.onboarding, .app-shell, .demo-banner').first(),
  ).toBeVisible({ timeout: 15_000 });
}

/**
 * Skip the marketplace onboarding (click "Пропустить, посмотрю сначала").
 * Only call this when the onboarding screen is visible.
 */
export async function skipOnboarding(page: Page): Promise<void> {
  const skipBtn = page.getByRole('button', { name: /Пропустить/i });
  await expect(skipBtn).toBeVisible({ timeout: 10_000 });
  await skipBtn.click();

  // After skip, the app should show the main inbox (app-shell)
  await expect(page.locator('.app-shell')).toBeVisible({ timeout: 10_000 });
}

/**
 * Full flow: register a new user and skip onboarding to get to the inbox.
 * Returns the credentials used so subsequent tests can re-login.
 */
export async function registerAndSkipToInbox(
  page: Page,
  options?: { email?: string; password?: string; name?: string },
): Promise<{ email: string; password: string; name: string }> {
  const creds = await registerUser(page, options);

  // If the onboarding screen is showing, skip it
  const onboarding = page.locator('.onboarding');
  if (await onboarding.isVisible().catch(() => false)) {
    await skipOnboarding(page);
  }

  return creds;
}

/**
 * Login and skip onboarding (for tests that need an existing user).
 */
export async function loginAndSkipToInbox(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await loginUser(page, email, password);

  // If the onboarding screen is showing, skip it
  const onboarding = page.locator('.onboarding');
  if (await onboarding.isVisible().catch(() => false)) {
    await skipOnboarding(page);
  }
}

/**
 * Navigate to a workspace via the sidebar.
 * Available workspaces: 'messages' | 'analytics' | 'promo' | 'settings'
 */
export async function navigateToWorkspace(
  page: Page,
  workspace: 'messages' | 'analytics' | 'promo' | 'settings',
): Promise<void> {
  const labelMap: Record<string, string> = {
    messages: 'Сообщения',
    analytics: 'Аналитика',
    promo: 'Промокоды',
    settings: 'Настройки',
  };

  const label = labelMap[workspace];

  // Try sidebar first (desktop), then bottom nav (mobile fallback)
  const sidebarBtn = page.locator(`.sidebar-item .sidebar-label:has-text("${label}")`).first();
  const bottomNavBtn = page.locator(`.bottom-nav-item:has-text("${label}")`).first();

  if (await sidebarBtn.isVisible().catch(() => false)) {
    await sidebarBtn.click();
  } else if (await bottomNavBtn.isVisible().catch(() => false)) {
    await bottomNavBtn.click();
  } else {
    // Fallback: click by text on any visible button
    await page.getByRole('button', { name: new RegExp(label, 'i') }).first().click();
  }
}
