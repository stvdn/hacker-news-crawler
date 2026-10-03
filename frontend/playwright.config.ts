import { defineConfig, devices } from "@playwright/test";
import { testApiPort, testApiUrl, testWebPort, testWebUrl } from "./test-config";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: testWebUrl,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" } },
  ],
  webServer: [
    {
      command: `uv run --locked uvicorn tests.browser_app:app --host 127.0.0.1 --port ${testApiPort}`,
      cwd: "../backend",
      url: `${testApiUrl}/health`,
      reuseExistingServer: false,
    },
    {
      command: `pnpm start --port ${testWebPort}`,
      url: `${testWebUrl}/health`,
      env: { API_BASE_URL: testApiUrl, NEXT_TELEMETRY_DISABLED: "1" },
      reuseExistingServer: false,
    },
  ],
});
