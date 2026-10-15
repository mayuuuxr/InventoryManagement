// Playwright for nibba (Django templates, no SPA).
// Local + CI: retries, traces on failure, screenshots.
const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests',
  timeout: 30000,
  retries: process.env.CI ? 2 : 1,
  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: process.env.CI ? undefined : {
    command: 'cmd /c "..\\run_pc.bat"',
    url: 'http://127.0.0.1:8000/accounts/login/',
    timeout: 90000,
    reuseExistingServer: true,
  },
});
