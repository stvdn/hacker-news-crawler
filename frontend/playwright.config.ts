import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" } },
  ],
  webServer: [
    {
      command: "uv run --locked uvicorn tests.browser_app:app --host 127.0.0.1 --port 8100",
      cwd: "../backend",
      url: "http://127.0.0.1:8100/health",
      reuseExistingServer: false,
    },
    {
      command: "pnpm start --port 3100",
      url: "http://127.0.0.1:3100/health",
      env: { API_BASE_URL: "http://127.0.0.1:8100", NEXT_TELEMETRY_DISABLED: "1" },
      reuseExistingServer: false,
    },
  ],
});
