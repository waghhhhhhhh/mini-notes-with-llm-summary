import { expect, test } from "@playwright/test";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "../..");
const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 5195);
const BASE_URL = `http://127.0.0.1:${PORT}`;

let harness: ChildProcess | undefined;

async function waitForHarness(): Promise<void> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (harness?.exitCode != null) {
      throw new Error(`Anna harness exited with code ${harness.exitCode}`);
    }
    try {
      const response = await fetch(`${BASE_URL}/api/config`);
      if (response.ok) {
        return;
      }
    } catch {
      // The bridge is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("Anna harness did not become ready");
}

test.beforeAll(async () => {
  harness = spawn(
    process.execPath,
    [
      path.join(ROOT, "scripts", "anna-dev.mjs"),
      "--port",
      String(PORT),
      "--no-watch",
    ],
    {
      cwd: ROOT,
      env: { ...process.env, BROWSER: "none" },
      stdio: "ignore",
      detached: process.platform !== "win32",
    },
  );
  await waitForHarness();
});

test.afterAll(async () => {
  if (!harness || harness.exitCode != null) {
    return;
  }
  if (process.platform === "win32") {
    spawnSync(
      "taskkill",
      ["/PID", String(harness.pid), "/T", "/F"],
      { stdio: "ignore" },
    );
  } else {
    process.kill(-harness.pid!, "SIGTERM");
  }
  await Promise.race([
    once(harness, "exit"),
    new Promise((resolve) => setTimeout(resolve, 10_000)),
  ]);
});

test("creates, deletes, and summarizes notes through Anna Host APIs", async ({
  page,
}) => {
  await page.goto(BASE_URL);
  await expect(page.locator("#status")).toHaveText("connected");

  const app = page.frameLocator("#app");
  await expect(app.getByRole("heading", { name: "Mini Notes" })).toBeVisible();

  const input = app.getByPlaceholder("Write a short note");
  await input.fill("Prepare the interview walkthrough");
  await app.getByRole("button", { name: "Save" }).click();

  await expect(app.getByText("Prepare the interview walkthrough")).toBeVisible();
  await expect(input).toHaveValue("");
  await expect(page.locator("#log")).toContainText("storage.set");

  await app.getByRole("button", { name: "Delete note 1" }).click();
  await expect(app.getByText("No notes yet.")).toBeVisible();
  await expect(page.locator("#log")).toContainText("storage.get");

  await input.fill("Follow up with the customer tomorrow");
  await app.getByRole("button", { name: "Save" }).click();
  await app.getByRole("button", { name: "Summarize" }).click();

  await expect(app.getByRole("alert")).toContainText(
    "harness started with --no-llm",
  );
  await expect(page.locator("#log")).toContainText("tools.invoke");

  await page.locator("#log .log-row").last().scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "test-results/mini-notes-harness.png",
    fullPage: true,
  });
});
