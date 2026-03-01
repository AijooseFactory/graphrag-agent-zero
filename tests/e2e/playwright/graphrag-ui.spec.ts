import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

/**
 * GraphRAG UI E2E Test
 * Assumes dev container is running on http://localhost:8087
 */
test.describe('GraphRAG Web UI E2E', () => {
    const url = 'http://localhost:8087';

    test('Page loads and chat round-trip works', async ({ page }) => {
        // 1. Navigate to Web UI
        await page.goto(url);
        await expect(page).toHaveTitle(/Agent Zero/i);

        // 2. Start a new chat (if needed, usually loads default)
        // Basic check for input field
        const input = page.locator('textarea[placeholder*="Type your message here"]');
        await expect(input).toBeVisible();

        // 3. Send a test message
        const testMessage = 'E2E ping — verify GraphRAG presence';
        await input.fill(testMessage);
        await page.keyboard.press('Enter');

        // 4. Wait for response (look for common response container)
        // Note: Adjust selector based on actual Agent Zero UI if it changes
        const response = page.locator('.message-content, .chat-message').last();
        await expect(response).toBeVisible({ timeout: 30000 });

        // 5. Verify log markers via Docker (Server-side validation)
        // This proves the extension actually fired behind the scenes
        const logs = execSync('docker logs --tail 20 agent-zero-graphrag-dev').toString();
        expect(logs).toContain('GRAPHRAG_EXTENSION_EXECUTED');

        console.log('UI Round-trip and Log Markers verified.');
    });
});
