import { defineConfig } from "@playwright/test";

const port = Number(process.env.PLAYWRIGHT_PORT ?? 5195);
const channel =
  process.env.PLAYWRIGHT_CHANNEL ??
  (process.platform === "win32" ? "msedge" : "chrome");

export default defineConfig({
  testDir: "tests/browser",
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    channel,
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
