import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cli = path.join(root, "node_modules", "@anna-ai", "cli", "dist", "cli.js");
const cache = path.join(root, ".cache");
const slug = "mini-notes-with-llm-summary";

const child = spawn(
  process.execPath,
  [cli, "dev", "--no-llm", "--slug", slug, ...process.argv.slice(2)],
  {
    cwd: root,
    env: {
      ...process.env,
      UV_CACHE_DIR: path.join(cache, "uv"),
      UV_PYTHON_INSTALL_DIR: path.join(cache, "python"),
      UV_PYTHON_DOWNLOADS: "never",
      UV_TOOL_DIR: path.join(cache, "uv-tools"),
      UV_TOOL_BIN_DIR: path.join(cache, "uv-bin"),
    },
    stdio: "inherit",
    detached: process.platform !== "win32",
  },
);

let stopping = false;

function stopChild(signal) {
  if (stopping || child.exitCode !== null) {
    return;
  }
  stopping = true;
  if (process.platform === "win32") {
    spawnSync(
      "taskkill",
      ["/PID", String(child.pid), "/T", "/F"],
      { stdio: "ignore" },
    );
  } else {
    process.kill(-child.pid, signal);
  }
}

process.on("SIGINT", () => {
  stopChild("SIGINT");
});
process.on("SIGTERM", () => {
  stopChild("SIGTERM");
});

child.on("exit", (code, signal) => {
  if (stopping) {
    process.exit(0);
  }
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
