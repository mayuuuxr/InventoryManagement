// Auth fixture: logs in once per worker, reuses session (no repeat logins).
// Seed: create owner + staff PINs via Django shell before running:
//   venv\Scripts\python manage.py createsuperuser  (owner)
// Test data cleanup: tests use unique site/material names per run (timestamped)
// so runs are isolated; a teardown script deletes `E2E-*` rows via shell.
const { test: base } = require('@playwright/test');
const fs = require('fs');
const AUTH = '.auth/owner.json';
const test = base.extend({
  authedPage: async ({ browser }, use) => {
    await fs.promises.mkdir('.auth', { recursive: true });
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    let ok = false;
    try {
      const saved = await fs.promises.readFile(AUTH);
      await ctx.addCookies(JSON.parse(saved));
      await page.goto('/sites/');
      ok = page.url().includes('/sites');
    } catch {}
    if (!ok) {
      await page.goto('/accounts/login/');
      await page.getByLabel(/username/i).fill(process.env.E2E_USER || 'owner');
      await page.getByLabel(/pin|password/i).fill(process.env.E2E_PASS || 'owner1234');
      await page.getByRole('button', { name: /sign in|log in/i }).click();
      await page.waitForURL('**/sites/**');
      await ctx.storageState({ path: '.auth/state.json' });
    }
    await use(page);
    await ctx.close();
  },
});
module.exports = { test };
