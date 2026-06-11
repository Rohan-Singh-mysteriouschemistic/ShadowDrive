import { test, expect } from '@playwright/test';

test.describe('Suite 3: UI Reactivity & Disconnects', () => {
  test('SSE Connection Drop and Recovery', async ({ page }) => {
    // 1. Setup Auth
    await page.addInitScript(() => {
      window.localStorage.setItem('shadowdrive_token', 'mock_token');
    });

    let sseFails = true;

    // 2. Intercept SSE Stream (The Injection)
    await page.route('**/events/stream?token=*', async (route) => {
      if (sseFails) {
        // Return 502 Bad Gateway to simulate proxy/server crash
        await route.fulfill({
          status: 502,
          contentType: 'text/plain',
          body: 'Bad Gateway',
        });
      } else {
        // Mock a successful SSE response injecting a new file event
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          body: 'event: file_created\ndata: {"type": "file_created", "data": {"file_path": "recovered.txt"}}\n\n',
        });
      }
    });

    // 3. Mock Initial Metadata
    await page.route('**/sync/metadata', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, file_path: 'initial.txt', size_bytes: 100, upload_status: 'complete' }
        ]),
      });
    });

    // 4. The Flow: Navigate to Vault
    await page.goto('http://localhost:5173/vault');

    // Wait for the initial file to appear
    await expect(page.locator('text=initial.txt')).toBeVisible();

    // 5. The Assertion (Part 1): UI stays responsive despite 502s
    // The UI is now attempting to connect to /events/stream and getting 502s behind the scenes.
    await expect(page.locator('text=initial.txt')).toBeVisible();
    
    // Simulate outage duration
    await page.waitForTimeout(3000);

    // 6. The Recovery
    sseFails = false;

    // Update the metadata mock to return the new file when the SSE event triggers a refresh
    await page.route('**/sync/metadata', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, file_path: 'initial.txt', size_bytes: 100, upload_status: 'complete' },
          { id: 2, file_path: 'recovered.txt', size_bytes: 200, upload_status: 'complete' }
        ]),
      });
    });

    // 7. The Assertion (Part 2): Eventual Consistency
    // Wait for the reconnect logic to kick in, receive the mock SSE event, and fetch the new metadata
    await expect(page.locator('text=recovered.txt')).toBeVisible({ timeout: 15000 });
  });
});
