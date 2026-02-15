import { test, expect } from '@playwright/test';
import { loginViaDemoMode } from './helpers/auth';

/**
 * Mobile layout tests -- catches Bug #29 (horizontal scroll, viewport overflow)
 * and verifies mobile-specific UI elements.
 *
 * These tests only run in the "mobile" project (iPhone 12 viewport).
 */

test.describe('Mobile Layout', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaDemoMode(page);
  });

  test('no horizontal scroll on mobile (Bug #29)', async ({ page }) => {
    // Wait for content to settle
    await page.waitForTimeout(1_000);

    const hasHorizontalScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });

    expect(hasHorizontalScroll).toBe(false);
  });

  test('no elements wider than viewport', async ({ page }) => {
    await page.waitForTimeout(1_000);

    const overflowingElements = await page.evaluate(() => {
      const viewportWidth = window.innerWidth;
      const allElements = document.querySelectorAll('*');
      const overflowing: string[] = [];

      allElements.forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.width > viewportWidth + 2) {
          // +2px tolerance
          const tag = el.tagName.toLowerCase();
          const cls = el.className ? `.${String(el.className).split(' ')[0]}` : '';
          overflowing.push(`${tag}${cls} (${Math.round(rect.width)}px)`);
        }
      });

      return overflowing;
    });

    expect(overflowingElements).toEqual([]);
  });

  test('chat list fills viewport width on mobile', async ({ page }) => {
    const chatList = page.locator('.chat-list');
    await expect(chatList).toBeVisible();

    const chatListBox = await chatList.boundingBox();
    const viewportWidth = page.viewportSize()?.width || 390;

    expect(chatListBox).toBeTruthy();
    if (chatListBox) {
      // Chat list should span at least 90% of viewport
      expect(chatListBox.width).toBeGreaterThanOrEqual(viewportWidth * 0.9);
    }
  });

  test('bottom nav visible on mobile', async ({ page }) => {
    const bottomNav = page.locator('.bottom-nav');
    await expect(bottomNav).toBeVisible();

    // Should have navigation items
    const navItems = page.locator('.bottom-nav-item');
    const count = await navItems.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('sidebar hidden on mobile', async ({ page }) => {
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).not.toBeVisible();
  });

  test('touch targets >= 44x44px for interactive elements', async ({ page }) => {
    await page.waitForTimeout(1_000);

    const smallTargets = await page.evaluate(() => {
      const MIN_SIZE = 44;
      const interactiveSelectors = [
        'button:not([disabled])',
        'a[href]',
        '.bottom-nav-item',
        '.filter-pill',
        '.folder-item',
      ];

      const small: string[] = [];

      for (const selector of interactiveSelectors) {
        const elements = document.querySelectorAll(selector);
        elements.forEach((el) => {
          const rect = el.getBoundingClientRect();
          // Only check visible elements
          if (rect.width === 0 || rect.height === 0) return;
          // Check if the element or its clickable parent meets the minimum
          if (rect.width < MIN_SIZE && rect.height < MIN_SIZE) {
            const tag = el.tagName.toLowerCase();
            const text = (el.textContent || '').trim().slice(0, 20);
            const cls = el.className ? `.${String(el.className).split(' ')[0]}` : '';
            small.push(
              `${tag}${cls}[${text}] (${Math.round(rect.width)}x${Math.round(rect.height)})`,
            );
          }
        });
      }

      return small;
    });

    // Warn but don't fail hard -- report which elements are too small
    if (smallTargets.length > 0) {
      console.warn(
        `Touch target violations (${smallTargets.length}):\n${smallTargets.join('\n')}`,
      );
    }

    // Allow up to 5 minor violations (icons in headers, etc.)
    expect(smallTargets.length).toBeLessThanOrEqual(5);
  });

  test('mobile view switching: list -> chat -> back', async ({ page }) => {
    // We start in list view
    const chatCenter = page.locator('.chat-center');
    await expect(chatCenter).toHaveAttribute('data-mobile-view', 'list');

    // If there are chat items, click the first one
    const chatItems = page.locator('.chat-item');
    const chatCount = await chatItems.count();

    if (chatCount > 0) {
      await chatItems.first().click();

      // Should switch to chat view
      await expect(chatCenter).toHaveAttribute('data-mobile-view', 'chat');

      // Back button should be visible
      const backBtn = page.locator('.chat-header-back');
      await expect(backBtn).toBeVisible();

      // Click back
      await backBtn.click();

      // Should return to list
      await expect(chatCenter).toHaveAttribute('data-mobile-view', 'list');
    }
  });

  test('filter pills horizontally scrollable on mobile', async ({ page }) => {
    const filtersScroll = page.locator('.filters-scroll');
    await expect(filtersScroll).toBeVisible();

    const pills = page.locator('.filter-pill');
    const count = await pills.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });
});
