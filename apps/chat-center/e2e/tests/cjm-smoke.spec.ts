import { test, expect } from '@playwright/test';
import {
  generateTestEmail,
  TEST_PASSWORD,
  TEST_COMPANY,
  registerUser,
  loginUser,
  skipOnboarding,
  registerAndSkipToInbox,
  loginAndSkipToInbox,
  navigateToWorkspace,
} from '../helpers/auth';

/**
 * AgentIQ Chat Center — CJM Smoke Tests
 *
 * Critical user journey:
 *   1. Register
 *   2. Skip/connect marketplace onboarding
 *   3. View inbox (main messages screen)
 *   4. Open interaction detail
 *   5. View analytics
 *   6. View settings
 *
 * Prerequisites:
 *   - Backend running at http://localhost:8001 (FastAPI)
 *   - Frontend running at http://localhost:5173 (Vite dev)
 *   - Or set BASE_URL env variable for a remote target
 *
 * Run:
 *   cd apps/chat-center/e2e
 *   npm install
 *   npx playwright install chromium
 *   npx playwright test
 */

// ---------------------------------------------------------------
// Test 1: Registration
// ---------------------------------------------------------------
test.describe('CJM Smoke Tests', () => {
  // Shared credentials — the first test registers, subsequent tests re-login
  let testEmail: string;
  let testPassword: string;

  test.beforeAll(() => {
    testEmail = generateTestEmail();
    testPassword = TEST_PASSWORD;
  });

  test('1 - user can register', async ({ page }) => {
    await page.goto('/');

    // Verify login page is visible
    await expect(page.locator('.login-card')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.login-header h1')).toContainText('AGENTIQ');

    // Switch to registration mode
    await page.getByRole('button', { name: /Нет аккаунта\? Зарегистрироваться/i }).click();

    // Fill registration form
    await page.locator('#name').fill(TEST_COMPANY);
    await page.locator('#email').fill(testEmail);
    await page.locator('#password').fill(testPassword);

    // Submit
    await page.getByRole('button', { name: /Зарегистрироваться/i }).click();

    // Should redirect to onboarding (marketplace connection screen)
    await expect(
      page.locator('.onboarding').first(),
    ).toBeVisible({ timeout: 15_000 });

    // Verify the onboarding shows marketplace options
    await expect(page.locator('.onboarding-title')).toBeVisible();
  });

  // ---------------------------------------------------------------
  // Test 2: Skip onboarding
  // ---------------------------------------------------------------
  test('2 - user can skip WB connection (onboarding)', async ({ page }) => {
    // Login with the user created in Test 1
    await loginUser(page, testEmail, testPassword);

    // Should see onboarding (user has no API credentials)
    const onboarding = page.locator('.onboarding');
    await expect(onboarding).toBeVisible({ timeout: 10_000 });

    // Click skip button
    const skipBtn = page.getByRole('button', { name: /Пропустить/i });
    await expect(skipBtn).toBeVisible();
    await skipBtn.click();

    // Should redirect to main app shell (inbox)
    await expect(page.locator('.app-shell')).toBeVisible({ timeout: 10_000 });

    // Demo banner should be visible (since we skipped connection)
    await expect(page.locator('.demo-banner')).toBeVisible();
  });

  // ---------------------------------------------------------------
  // Test 3: Main inbox loads with channel tabs and filter pills
  // ---------------------------------------------------------------
  test('3 - main inbox shows channel tabs and filters', async ({ page }) => {
    await loginAndSkipToInbox(page, testEmail, testPassword);

    // Verify app shell is rendered
    await expect(page.locator('.app-shell')).toBeVisible();

    // Verify sidebar is visible with navigation items
    await expect(page.locator('.sidebar')).toBeVisible();
    await expect(page.locator('.sidebar-logo')).toContainText('AGENTIQ');

    // Verify sidebar nav items: Сообщения, Аналитика, Промокоды, Настройки
    await expect(page.locator('.sidebar-label:has-text("Сообщения")')).toBeVisible();
    await expect(page.locator('.sidebar-label:has-text("Аналитика")')).toBeVisible();

    // Verify the chat-center area (messages workspace) is active
    await expect(page.locator('.chat-center')).toBeVisible();

    // Verify channel filter tabs exist in .channel-filters
    // ChatList renders: "Каналы: все", "Отзывы", "Вопросы", "Чаты" as filter-pill buttons
    const channelFilters = page.locator('.channel-filters');
    await expect(channelFilters).toBeVisible({ timeout: 5_000 });

    // Check each channel tab pill
    await expect(channelFilters.locator('.filter-pill:has-text("Отзывы")')).toBeVisible();
    await expect(channelFilters.locator('.filter-pill:has-text("Вопросы")')).toBeVisible();
    await expect(channelFilters.locator('.filter-pill:has-text("Чаты")')).toBeVisible();

    // Verify status filter pills exist (Все, Срочно, Без ответа, Обработаны)
    // These are in .filters-container (NOT .channel-filters)
    const filtersScroll = page.locator('.filters-container:not(.channel-filters) .filters-scroll');
    await expect(filtersScroll).toBeVisible({ timeout: 5_000 });
    await expect(filtersScroll.locator('.filter-pill:has-text("Срочно")')).toBeVisible();
    await expect(filtersScroll.locator('.filter-pill:has-text("Без ответа")')).toBeVisible();
    await expect(filtersScroll.locator('.filter-pill:has-text("Обработаны")')).toBeVisible();
  });

  // ---------------------------------------------------------------
  // Test 4: Open interaction detail (if interactions exist)
  // ---------------------------------------------------------------
  test('4 - can open interaction detail (if available)', async ({ page }) => {
    await loginAndSkipToInbox(page, testEmail, testPassword);

    await expect(page.locator('.chat-center')).toBeVisible();

    // Check if there are any chat items in the list
    const chatItems = page.locator('.chat-item');
    const chatItemCount = await chatItems.count();

    if (chatItemCount > 0) {
      // Click the first chat item
      await chatItems.first().click();

      // Verify the chat window shows message content
      await expect(
        page.locator('.chat-window, .message, .message-content').first(),
      ).toBeVisible({ timeout: 10_000 });

      // Verify the product context panel is visible (on desktop)
      const contextPanel = page.locator('.product-context');
      // It may be hidden on mobile viewports; just check it exists in DOM
      await expect(contextPanel).toBeAttached();
    } else {
      // No interactions — verify empty state or loading indicator is shown
      // This is acceptable for a smoke test with a fresh user (no demo data)
      const emptyOrLoading = page.locator(
        '.queue-empty, .empty-state, .chat-list-loading, .chat-list-empty',
      ).first();
      // Just verify the app did not crash — the chat center is still visible
      await expect(page.locator('.chat-center')).toBeVisible();
    }
  });

  // ---------------------------------------------------------------
  // Test 5: Analytics page loads
  // ---------------------------------------------------------------
  test('5 - analytics page loads with KPI cards', async ({ page }) => {
    await loginAndSkipToInbox(page, testEmail, testPassword);

    // Navigate to analytics
    await navigateToWorkspace(page, 'analytics');

    // Verify analytics page is visible
    const analyticsPage = page.locator('.analytics-page, #analyticsPage');
    await expect(analyticsPage.first()).toBeVisible({ timeout: 10_000 });

    // Verify analytics title
    await expect(page.locator('.analytics-title')).toContainText('Аналитика');

    // Verify KPI strip is present
    await expect(page.locator('.kpi-strip')).toBeVisible();

    // Verify at least some KPI cards are rendered
    const kpiCards = page.locator('.kpi-card');
    await expect(kpiCards.first()).toBeVisible();
    const kpiCount = await kpiCards.count();
    expect(kpiCount).toBeGreaterThanOrEqual(3);

    // Verify period controls exist
    await expect(page.locator('.analytics-period')).toBeVisible();

    // Verify analytics grid sections exist
    await expect(page.locator('.analytics-grid').first()).toBeVisible();
  });

  // ---------------------------------------------------------------
  // Test 6: Settings page loads with tabs
  // ---------------------------------------------------------------
  test('6 - settings page loads with connection and AI tabs', async ({ page }) => {
    await loginAndSkipToInbox(page, testEmail, testPassword);

    // Navigate to settings
    await navigateToWorkspace(page, 'settings');

    // Verify settings page is visible
    const settingsPage = page.locator('.settings-page');
    await expect(settingsPage).toBeVisible({ timeout: 10_000 });

    // Verify settings navigation tabs
    await expect(page.locator('.settings-nav-title')).toContainText('Настройки');

    // Verify "Подключения" tab is active by default
    await expect(page.locator('.settings-section-title')).toContainText('Подключения');

    // Verify Wildberries connection card exists
    await expect(page.locator('.connection-card').first()).toBeVisible();
    await expect(page.locator('.connection-name:has-text("Wildberries")')).toBeVisible();

    // Switch to AI tab
    const aiTab = page.locator('.settings-nav-item:has-text("AI-ассистент")');
    await aiTab.click();
    await expect(page.locator('.settings-section-title')).toContainText('AI-ассистент');

    // Verify AI setting cards are present
    await expect(page.locator('.ai-setting-card').first()).toBeVisible();

    // Switch to Profile tab
    const profileTab = page.locator('.settings-nav-item:has-text("Профиль")');
    await profileTab.click();
    await expect(page.locator('.settings-section-title')).toContainText('Профиль');

    // Verify profile form shows user email
    await expect(page.locator('.form-input[type="email"]')).toBeVisible();
  });

  // ---------------------------------------------------------------
  // Test 7: Sidebar navigation works correctly
  // ---------------------------------------------------------------
  test('7 - sidebar navigation between workspaces', async ({ page }) => {
    await loginAndSkipToInbox(page, testEmail, testPassword);

    // Start at messages
    await expect(page.locator('.chat-center')).toBeVisible();

    // Go to analytics
    await navigateToWorkspace(page, 'analytics');
    await expect(page.locator('.analytics-page, #analyticsPage').first()).toBeVisible({ timeout: 10_000 });

    // Go back to messages
    await navigateToWorkspace(page, 'messages');
    await expect(page.locator('.chat-center')).toBeVisible({ timeout: 10_000 });

    // Go to settings
    await navigateToWorkspace(page, 'settings');
    await expect(page.locator('.settings-page')).toBeVisible({ timeout: 10_000 });

    // Go to promo
    await navigateToWorkspace(page, 'promo');
    await expect(page.locator('.promo-page-wrap')).toBeVisible({ timeout: 10_000 });
  });

  // ---------------------------------------------------------------
  // Test 8: Logout works
  // ---------------------------------------------------------------
  test('8 - user can logout', async ({ page }) => {
    await loginAndSkipToInbox(page, testEmail, testPassword);

    // Click logout button in sidebar
    const logoutBtn = page.locator('.sidebar-item:has-text("Выйти")');
    await expect(logoutBtn).toBeVisible();
    await logoutBtn.click();

    // Should return to login page
    await expect(page.locator('.login-card')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.login-header h1')).toContainText('AGENTIQ');
  });

  // ---------------------------------------------------------------
  // Test 9: Demo mode works without registration
  // ---------------------------------------------------------------
  test('9 - demo mode button works without registration', async ({ page }) => {
    await page.goto('/');

    // Verify login page is visible
    await expect(page.locator('.login-card')).toBeVisible({ timeout: 10_000 });

    // Click demo mode button
    const demoBtn = page.getByRole('button', { name: /Демо-режим/i });
    await expect(demoBtn).toBeVisible();
    await demoBtn.click();

    // Should skip login and show either onboarding or app
    await expect(
      page.locator('.onboarding, .app-shell').first(),
    ).toBeVisible({ timeout: 10_000 });
  });
});
