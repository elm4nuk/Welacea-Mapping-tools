import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  webServer: process.env.WALLACEA_E2E_START_WEB ? {
    command: 'pnpm dev --port 5174',
    url: process.env.WALLACEA_E2E_WEB_URL ?? 'http://127.0.0.1:5174',
    reuseExistingServer: false,
    timeout: 30_000,
  } : undefined,
  use: { baseURL: process.env.WALLACEA_E2E_WEB_URL ?? 'http://127.0.0.1:5174',
    trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1600, height: 1000 } } },
    { name: 'tablet', use: { ...devices['Desktop Chrome'], viewport: { width: 820, height: 1180 } } },
    { name: 'mobile', use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
