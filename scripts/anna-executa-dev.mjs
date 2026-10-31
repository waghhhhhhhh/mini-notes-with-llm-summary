import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cli = path.join(root, "node_modules", "@anna-ai", "cli", "dist", "cli.js");
const cache = path.join(root, ".cache");

const child = spawn(
  process.execPath,
  [
    cli,
    "executa",
    "dev",
    "--dir",
    path.join(root, "executas", "mini-notes-summarizer"),
    "--mock-sampling",
    path.join(root, "fixtures", "sampling", "create-message.jsonl"),
    "--no-agent",
    "--no-image",
    "--no-upload",
    "--storage",
    "off",
    "--invoke",
    "summarize",
    "--args",
    JSON.stringify({
      notes: [
        { seq: 1, text: "Follow up with the customer tomorrow." },
        { seq: 2, text: "Fix the login bug." },
      ],
    }),
    "--json",
    ...process.argv.slice(2),
  ],
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
  },
);

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

