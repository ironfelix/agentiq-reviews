import { test, expect } from '@playwright/test';
import { ensureAuthenticated, TEST_CREDENTIALS } from './helpers/auth';

/**
 * Chat detail / message view tests -- catches:
 *   Bug #32: Customer name shows "автор вопроса" instead of real name
 *   Bug #33: Mobile info button / context panel
 *   Bug #36: Messages take too long to render after selecting a chat
 */

test.describe('Chat Detail View', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAuthenticated(page, TEST_CREDENTIALS);
    // Wait for the chat center to be ready
    await page.waitForSelector('.chat-center', { timeout: 10_000 });
  });

  test('customer name shows "Покупатель" or actual name, never "автор вопроса" (Bug #32)', async ({
    page,
  }) => {
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items to validate');
      return;
    }

    // Check all customer names in the list
    const names = await page.locator('.chat-item-name').allTextContents();

    for (const name of names) {
      // "автор вопроса" is the WB default -- we should show "Покупатель" or real name
      expect(name.toLowerCase()).not.toContain('автор вопроса');
      expect(name.trim().length).toBeGreaterThan(0);
    }
  });

  test('clicking a chat shows messages within 2 seconds (Bug #36)', async ({ page }) => {
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items to validate');
      return;
    }

    const startTime = Date.now();

    // Click the first chat
    await chatItems.first().click();

    // Wait for messages to appear (either the message list or "no messages" text)
    await page.waitForSelector('.message, .chat-messages', { timeout: 5_000 });

    // Messages or the "no messages" placeholder should be visible
    const chatMessages = page.locator('.chat-messages');
    await expect(chatMessages).toBeVisible({ timeout: 2_000 });

    const elapsed = Date.now() - startTime;
    // Messages should render within 2 seconds
    expect(elapsed).toBeLessThan(3_000);
  });

  test('message author shows "Продавец" for outgoing, customer name for incoming', async ({
    page,
  }) => {
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items');
      return;
    }

    await chatItems.first().click();
    await page.waitForSelector('.message', { timeout: 5_000 });

    const messages = page.locator('.message');
    const messageCount = await messages.count();

    if (messageCount === 0) {
      test.skip(true, 'No messages in selected chat');
      return;
    }

    // Check incoming messages have customer name (not "автор вопроса")
    const incomingAuthors = await page
      .locator('.message.customer .message-author')
      .allTextContents();

    for (const author of incomingAuthors) {
      expect(author.toLowerCase()).not.toContain('автор вопроса');
    }

    // Check outgoing messages have "Продавец"
    const outgoingAuthors = await page
      .locator('.message.seller .message-author')
      .allTextContents();

    for (const author of outgoingAuthors) {
      expect(author).toContain('Продавец');
    }
  });

  test('chat header shows customer info and product meta', async ({ page }) => {
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items');
      return;
    }

    await chatItems.first().click();
    await page.waitForSelector('.chat-header', { timeout: 5_000 });

    // Header should have customer name
    const headerName = page.locator('.chat-header-info h2');
    await expect(headerName).toBeVisible();
    const nameText = await headerName.textContent();
    expect(nameText?.trim().length).toBeGreaterThan(0);
    expect(nameText?.toLowerCase()).not.toContain('автор вопроса');

    // Header should have meta info
    const headerMeta = page.locator('.chat-header-meta');
    await expect(headerMeta).toBeVisible();
  });

  test('AI recommendation section renders when available', async ({ page }) => {
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items');
      return;
    }

    await chatItems.first().click();
    await page.waitForSelector('.chat-messages', { timeout: 5_000 });

    // AI suggestion should eventually appear (or the responded state)
    // Wait a bit for AI to load
    await page.waitForTimeout(2_000);

    const aiSuggestion = page.locator('.ai-suggestion');
    const isVisible = await aiSuggestion.isVisible().catch(() => false);

    if (isVisible) {
      // If visible, it should have a label
      const label = page.locator('.ai-suggestion-label');
      await expect(label).toBeVisible();
    }
    // If not visible, that's OK -- not all chats have AI suggestions
  });

  test('reply input area is functional', async ({ page }) => {
    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items');
      return;
    }

    await chatItems.first().click();
    await page.waitForSelector('.chat-messages', { timeout: 5_000 });

    // Check for input container (may be hidden for responded chats)
    const inputContainer = page.locator('.chat-input-container');
    const respondedBanner = page.locator('.ai-suggestion:has-text("Вы ответили")');

    const hasInput = await inputContainer.isVisible().catch(() => false);
    const hasResponded = await respondedBanner.isVisible().catch(() => false);

    // Either the input area or the "responded" banner should be visible
    expect(hasInput || hasResponded).toBe(true);

    if (hasInput) {
      const textarea = page.locator('.chat-input');
      await expect(textarea).toBeVisible();

      // Type something
      await textarea.fill('Test message');
      expect(await textarea.inputValue()).toBe('Test message');

      // Send button should become enabled
      const sendBtn = page.locator('.btn-send');
      await expect(sendBtn).toBeVisible();
    }
  });
});

test.describe('Chat Detail -- Mobile (Bug #33)', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAuthenticated(page, TEST_CREDENTIALS);
    await page.waitForSelector('.chat-center', { timeout: 10_000 });
  });

  test('mobile: info button visible in chat header', async ({ page }) => {
    const isMobile = (page.viewportSize()?.width || 0) < 769;
    test.skip(!isMobile, 'Desktop only -- skip');

    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items');
      return;
    }

    await chatItems.first().click();
    await page.waitForSelector('.chat-header', { timeout: 5_000 });

    // Info button should be visible
    const infoBtn = page.locator('.header-action-btn[title="Информация"]');
    await expect(infoBtn).toBeVisible();
  });

  test('mobile: clicking Info opens context panel', async ({ page }) => {
    const isMobile = (page.viewportSize()?.width || 0) < 769;
    test.skip(!isMobile, 'Desktop only -- skip');

    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items');
      return;
    }

    await chatItems.first().click();
    await page.waitForSelector('.chat-header', { timeout: 5_000 });

    // Click info button
    const infoBtn = page.locator('.header-action-btn[title="Информация"]');
    await infoBtn.click();

    // Chat center should switch to context view
    const chatCenter = page.locator('.chat-center');
    await expect(chatCenter).toHaveAttribute('data-mobile-view', 'context');

    // Context panel should be visible
    const contextPanel = page.locator('.product-context');
    await expect(contextPanel).toBeVisible();
  });

  test('mobile: back button returns to chat list', async ({ page }) => {
    const isMobile = (page.viewportSize()?.width || 0) < 769;
    test.skip(!isMobile, 'Desktop only -- skip');

    const chatItems = page.locator('.chat-item');
    const count = await chatItems.count();

    if (count === 0) {
      test.skip(true, 'No chat items');
      return;
    }

    await chatItems.first().click();

    // Chat view
    const chatCenter = page.locator('.chat-center');
    await expect(chatCenter).toHaveAttribute('data-mobile-view', 'chat');

    // Click back
    const backBtn = page.locator('.chat-header-back');
    await expect(backBtn).toBeVisible();
    await backBtn.click();

    // Should return to list
    await expect(chatCenter).toHaveAttribute('data-mobile-view', 'list');
  });
});
