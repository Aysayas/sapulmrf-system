import { defineConfig, devices } from '@playwright/test'

// The test admin's login lives in the repo's git-ignored .env (E2E_ADMIN_USERNAME / E2E_ADMIN_PASSWORD).
process.loadEnvFile('../.env')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'html',
  use: {
    // 127.0.0.1, not localhost: another Vite server can hold [::1]:5174, and localhost resolves there first.
    baseURL: 'http://127.0.0.1:5174',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'mobile',
      testMatch: ['**/operator*.spec.ts'],
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } },
    },
    {
      name: 'desktop',
      testIgnore: ['**/operator*.spec.ts'],
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: {
    command: 'docker compose up -d',
    cwd: '..',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: true,
    timeout: 180_000,
  },
})
