import { test, expect } from '@playwright/test';

test('GraphRAG query works in dev container', async ({ page }) => {
    test.setTimeout(120000); // 2 minutes timeout for LLM inference
    // Go to the dev container UI
    await page.goto('http://localhost:8087/');

    // Wait for the chat input to be ready
    const chatInput = page.locator('textarea').first();
    await expect(chatInput).toBeAttached({ timeout: 10000 });

    // Type the test prompt
    const testPrompt = "Based on your memory, what are the core components of the AijooseFactory/graphrag-agent-zero extension, and how do they interact with Neo4j?";
    await chatInput.fill(testPrompt, { force: true });

    // Press Enter to send
    await chatInput.press('Enter');

    // Wait for the agent to start responding by waiting for a paragraph tag to appear inside the chat area
    const responseText = page.locator('p').last();
    await expect(responseText).toBeAttached({ timeout: 120000 });

    // Give it a few seconds for the user to read the success
    await page.waitForTimeout(5000);
});
