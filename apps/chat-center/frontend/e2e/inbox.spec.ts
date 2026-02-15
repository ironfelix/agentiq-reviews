import { test, expect } from '@playwright/test';
import { ensureAuthenticated, isBackendAvailable, TEST_CREDENTIALS } from './helpers/auth';

/**
 * Inbox / message list tests -- catches:
 *   Bug #28: Messages take 30s instead of 5s to appear
 *   Bug #30: Status dot colors wrong
 *   Bug #31: Channel tabs don't show badge counts
 *   Bug #34: Folder strip missing or misplaced
 *   Bug #37: Full-page spinner on tab switch
 */

test.describe('Inbox / Chat List', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAuthenticated(page, TEST_CREDENTIALS);
  });

  test('messages appear within 5 seconds of page load, not 30s (Bug #28)', async ({ page }) => {
    const backendUp = await isBackendAvailable(page);
    test.skip(!backendUp, 'Backend not available -- need real data');

    const startTime = Date.now();

    // Wait for either chat items or the empty state
    await page.waitForSelector('.chat-item, .empty-state', { timeout: 10_000 });

    const elapsed = Date.now() - startTime;

    // Messages should appear within 5 seconds
    expect(elapsed).toBeLessThan(5_000);
  });

  test('status dots have correct CSS classes based on chat_status (Bug #30)', async ({
    page,
  }) => {
    // Check that status-dot elements have the expected color classes
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items to validate');
      return;
    }

    // Collect all status dots and verify they have valid classes
    const dotClasses = await page.evaluate(() => {
      const dots = document.querySelectorAll('.status-dot');
      return Array.from(dots).map((dot) => dot.className);
    });

    const validStatuses = ['waiting', 'client-replied', 'responded', 'auto-response', 'risk'];

    for (const cls of dotClasses) {
      // Each dot must have at least one valid status modifier
      const hasValidStatus = validStatuses.some((s) => cls.includes(s));
      expect(hasValidStatus).toBe(true);
    }
  });

  test('status dot colors match design: waiting=yellow, responded=green, risk=red', async ({
    page,
  }) => {
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items to validate');
      return;
    }

    // Verify computed colors for each status type
    const colorMap = await page.evaluate(() => {
      const results: Record<string, string> = {};
      const statusClasses = ['waiting', 'responded', 'client-replied', 'auto-response'];

      for (const status of statusClasses) {
        const dot = document.querySelector(`.status-dot.${status}`);
        if (dot) {
          const bgColor = window.getComputedStyle(dot).backgroundColor;
          results[status] = bgColor;
        }
      }

      // Check risk dot separately
      const riskDot = document.querySelector('.status-dot.risk');
      if (riskDot) {
        results['risk'] = window.getComputedStyle(riskDot).backgroundColor;
      }

      return results;
    });

    // Verify known color values (from CSS: .status-dot.waiting = #f9ab00, etc.)
    if (colorMap['waiting']) {
      // #f9ab00 => rgb(249, 171, 0)
      expect(colorMap['waiting']).toContain('249');
    }
    if (colorMap['responded']) {
      // #34a853 => rgb(52, 168, 83)
      expect(colorMap['responded']).toContain('52');
    }
    if (colorMap['risk']) {
      // #ea4335 => rgb(234, 67, 53)
      expect(colorMap['risk']).toContain('234');
    }
    if (colorMap['client-replied']) {
      // #4285f4 => rgb(66, 133, 244)
      expect(colorMap['client-replied']).toContain('66');
    }
  });

  test('channel tabs (FolderStrip) show badge counts > 0 when items exist (Bug #31)', async ({
    page,
  }) => {
    const backendUp = await isBackendAvailable(page);
    test.skip(!backendUp, 'Backend not available -- need pipeline data');

    // Wait for data to load
    await page.waitForSelector('.chat-item, .empty-state', { timeout: 10_000 });

    // Check if any chat items exist
    const chatCount = await page.locator('.chat-item').count();
    if (chatCount === 0) {
      test.skip(true, 'No chats to validate badges');
      return;
    }

    // At least the "All" folder should show a badge
    const badges = page.locator('.folder-badge');
    const badgeCount = await badges.count();
    expect(badgeCount).toBeGreaterThan(0);

    // Verify the badge text is a number > 0
    const firstBadgeText = await badges.first().textContent();
    expect(firstBadgeText).toBeTruthy();
    const numericValue = parseInt(firstBadgeText || '0', 10);
    expect(numericValue).toBeGreaterThan(0);
  });

  test('folder strip appears in the correct position (Bug #34)', async ({ page }) => {
    const isMobile = (page.viewportSize()?.width || 0) < 769;

    if (isMobile) {
      // On mobile, FolderStrip.mobile is inside .chat-list-header
      const mobileStrip = page.locator('.folder-strip.mobile');
      await expect(mobileStrip).toBeVisible();
    } else {
      // On desktop, FolderStrip.desktop is a sibling of .chat-list
      const desktopStrip = page.locator('.folder-strip.desktop');
      await expect(desktopStrip).toBeVisible();
    }

    // Search input should always be visible
    const searchBox = page.locator('.search-box');
    await expect(searchBox).toBeVisible();
  });

  test('switching workspace tabs and back does not show full-page spinner (Bug #37)', async ({
    page,
  }) => {
    // Wait for initial load
    await page.waitForSelector('.chat-center', { timeout: 10_000 });
    await page.waitForTimeout(1_000);

    const isMobile = (page.viewportSize()?.width || 0) < 769;

    if (isMobile) {
      // Use bottom nav on mobile
      const analyticsBtn = page.locator('.bottom-nav-item:has-text("Аналитика")');
      await analyticsBtn.click();
      await page.waitForTimeout(500);

      // Switch back to messages
      const messagesBtn = page.locator('.bottom-nav-item:has-text("Сообщения")');
      await messagesBtn.click();
    } else {
      // Use sidebar on desktop
      const analyticsBtn = page.locator('.sidebar-item:has-text("Аналитика")');
      await analyticsBtn.click();
      await page.waitForTimeout(500);

      // Switch back
      const messagesBtn = page.locator('.sidebar-item:has-text("Сообщения")');
      await messagesBtn.click();
    }

    // After switching back, the chat-center should appear without a full-page spinner
    await expect(page.locator('.chat-center')).toBeVisible({ timeout: 2_000 });

    // The full-page spinner (.empty-state-icon.syncing inside .chat-list-content)
    // should NOT be showing if we had cached data
    // Give it a moment to settle
    await page.waitForTimeout(500);

    const isLoadingSpinner = await page
      .locator('.chat-list-content .empty-state-icon.syncing')
      .isVisible()
      .catch(() => false);

    // If there are already chats loaded, no spinner should appear
    const chatCount = await page.locator('.chat-item').count();
    if (chatCount > 0) {
      expect(isLoadingSpinner).toBe(false);
    }
  });

  test('channel filter preserves state across tab switches', async ({ page }) => {
    // Wait for initial load
    await page.waitForSelector('.chat-center', { timeout: 10_000 });

    // Click "Без ответа" filter
    const unansweredPill = page.locator('.filter-pill:has-text("Без ответа")');
    await unansweredPill.click();
    await expect(unansweredPill).toHaveClass(/active/);

    const isMobile = (page.viewportSize()?.width || 0) < 769;

    if (isMobile) {
      // Switch to analytics and back
      await page.locator('.bottom-nav-item:has-text("Аналитика")').click();
      await page.waitForTimeout(500);
      await page.locator('.bottom-nav-item:has-text("Сообщения")').click();
    } else {
      await page.locator('.sidebar-item:has-text("Аналитика")').click();
      await page.waitForTimeout(500);
      await page.locator('.sidebar-item:has-text("Сообщения")').click();
    }

    // Filter should still be active
    await expect(page.locator('.filter-pill:has-text("Без ответа")')).toHaveClass(/active/);
  });

  test('queue sections render in correct order: urgent > waiting > responded', async ({
    page,
  }) => {
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items to validate');
      return;
    }

    const queueLabels = await page.locator('.queue-label').allTextContents();

    // Verify order: if all 3 sections exist, they should be in this order
    const expectedOrder = ['В работе', 'Ожидают ответа', 'Все сообщения'];
    let lastFoundIndex = -1;

    for (const label of queueLabels) {
      const orderIndex = expectedOrder.indexOf(label);
      if (orderIndex !== -1) {
        expect(orderIndex).toBeGreaterThan(lastFoundIndex);
        lastFoundIndex = orderIndex;
      }
    }
  });
});
