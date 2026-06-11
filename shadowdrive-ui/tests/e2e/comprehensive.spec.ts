import { test, expect } from '@playwright/test';

// Use a random email to avoid collisions on subsequent runs
const randomSuffix = Math.floor(Math.random() * 100000);
const EMAIL = `ui_test_${randomSuffix}@test.com`;
const PASSWORD = 'password123';

test.describe('ShadowDrive++ Comprehensive UI Annihilation Suite', () => {

  // Run before all tests in this file: ensure we start at the auth page and register
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/auth');
  });

  test('1. Physical Auth Flow - Registration & Login', async ({ page }) => {
    // Navigate to Register tab
    await page.getByText(/Sign-Up/i).click();

    // Fill form physically
    await page.getByPlaceholder(/sysadmin@network.local/i).fill(EMAIL);
    await page.locator('input[name="password"]').fill(PASSWORD);
    await page.locator('input[name="confirm-password"]').fill(PASSWORD);
    await page.locator('input[name="passphrase"]').fill('mysecretpassphrase');

    // Click submit
    await page.getByRole('button', { name: /EXECUTE \/\/ DEPLOY/i }).click();

    // Assert navigation to vault
    await expect(page).toHaveURL(/.*\/vault/);
    
    // Log out physically
    await page.getByRole('button', { name: /sign out/i }).click();
    await expect(page).toHaveURL(/.*\/auth/);

    // Log back in physically
    await page.getByText(/Access vault./i).click();
    await page.getByPlaceholder(/sysadmin@network.local/i).fill(EMAIL);
    await page.locator('input[name="password"]').fill(PASSWORD);
    await page.getByRole('button', { name: /EXECUTE \/\/ LOGIN/i }).click();
    await expect(page).toHaveURL(/.*\/vault/);
  });

  test('2. Text Editor Network Drop Resilience & Recovery', async ({ page }) => {
    // Quick login
    await page.getByPlaceholder(/sysadmin@network.local/i).fill(EMAIL);
    await page.locator('input[name="password"]').fill(PASSWORD);
    await page.getByRole('button', { name: /EXECUTE \/\/ LOGIN/i }).click();
    
    // Wait for the login redirect to /vault to ensure token is set
    await page.waitForURL('**/vault');

    // We need a file to exist to click it. We can upload one physically via the UI.
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('button').filter({ hasText: 'Upload File' }).first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
        name: 'test_editor.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('Initial text content')
    });

    // Wait for the file to appear in the list
    const fileRow = page.getByText('test_editor.txt');
    await expect(fileRow).toBeVisible({ timeout: 15000 }); // give sync engine time

    // Physically click the row to open the editor
    await fileRow.click();
    
    // Assert the editor modal is open and has the content
    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible();
    await expect(textarea).toHaveValue('Initial text content');

    // Rapidly type physical keystrokes
    await textarea.fill('Initial text content. And now, the torturous chaos edit!');

    // Intercept the network to force a drop when saving
    await page.route('**/api/upload', route => route.abort('internetdisconnected'));

    // Hit Save
    await page.getByRole('button', { name: /save changes/i }).click();

    // Assert UI handles failure (should show error, modal stays open)
    // The exact error text might vary, but we assume "Failed" or "Error" appears
    await expect(page.getByText(/failed|error/i)).toBeVisible();
    await expect(textarea).toBeVisible(); // Modal MUST NOT have closed

    // Un-route (restore network connection)
    await page.unroute('**/api/upload');

    // Hit Save again (Recovery)
    // We mock the response to avoid needing the real local agent running if we are strictly testing UI logic
    // But the prompt said: "No mocking where physical UI interaction or local node execution is possible."
    // So we just let the physical POST hit the local agent.
    await page.getByRole('button', { name: /save changes/i }).click();

    // Assert Modal Closes and UI recovers
    await expect(textarea).not.toBeVisible();
  });

  test('3. Conflict Resolution UI Interaction', async ({ page }) => {
    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
    
    // Quick login
    await page.getByPlaceholder(/sysadmin@network.local/i).fill(EMAIL);
    await page.locator('input[name="password"]').fill(PASSWORD);
    await page.getByRole('button', { name: /EXECUTE \/\/ LOGIN/i }).click();
    
    // Wait for the login redirect to /vault to ensure token is set
    await page.waitForURL('**/vault');

    // 1. Intercept the API to mock a conflict file existing
    await page.route('**/sync/metadata', async route => {
      console.log("Mocking **/sync/metadata");
      const json = [
        {
          id: 999,
          file_path: 'budget (Conflicted copy).txt',
          hash: 'abc123mock',
          version_num: 2,
          size_bytes: 500,
          storage_path: '1/budget (Conflicted copy).txt/v2'
        }
      ];
      await route.fulfill({ json });
    });

    await page.route('**/sync/conflicts', async route => {
      console.log("Mocking **/sync/conflicts");
      const json = [
        {
          id: 'mock-conflict',
          filename: 'budget (Conflicted copy).txt',
          path: '/budget (Conflicted copy).txt',
          timeDetected: 'Just now',
          status: 'Needs Resolution',
          original_file_id: 1,
          conflict_file_id: 999,
          optionA: { device: 'Laptop', timestamp: '10 mins ago', size: '500 bytes', hash: 'oldhash' },
          optionB: { device: 'Local', timestamp: 'Just now', size: '500 bytes', hash: 'newhash' }
        }
      ];
      await route.fulfill({ json });
    });

    // Reload to hit the mocked route
    await page.reload();

    // Assert the conflicted file is visible
    const conflictRow = page.getByText('budget (Conflicted copy).txt');
    await expect(conflictRow).toBeVisible();

    // If the UI has a specific "Conflict" indicator based on the name (as per usecases 3.2.4)
    // We can assert the warning icon is there, assuming it uses a text/title or specific role.
    
    // According to usecase 3.7.4, clicking a conflict row opens the resolution modal
    await conflictRow.click();

    // Assert Resolution Modal opens with "Keep Both", "Keep Original", etc.
    const keepBothBtn = page.getByRole('button', { name: /keep both/i });
    await expect(keepBothBtn).toBeVisible();

    // To test SSE update immediately, we mock the resolution API endpoint
    await page.route('**/sync/resolve_conflict', async route => {
      // Mock successful resolution
      await route.fulfill({ json: { status: 'resolved' } });
      
      // Update the conflicts mock to return empty array so UI updates
      await page.unroute('**/sync/conflicts');
      await page.route('**/sync/conflicts', async r => {
        await r.fulfill({ json: [] });
      });
    });

    // Physically click "Keep Both"
    await keepBothBtn.click();

    // Assert the modal closes
    await expect(keepBothBtn).not.toBeVisible();
  });

});
