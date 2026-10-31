import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const python =
  process.platform === "win32"
    ? path.join(root, ".venv", "Scripts", "python.exe")
    : path.join(root, ".venv", "bin", "python");

if (!existsSync(python)) {
  console.error("Project Python environment is missing. Run `pnpm setup:python`.");
  process.exit(2);
}

const result = spawnSync(python, process.argv.slice(2), {
  cwd: root,
  env: {
    ...process.env,
    PYTHONUTF8: "1",
    UV_CACHE_DIR: path.join(root, ".cache", "uv"),
    UV_PYTHON_DOWNLOADS: "never",
  },
  stdio: "inherit",
});

if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);

