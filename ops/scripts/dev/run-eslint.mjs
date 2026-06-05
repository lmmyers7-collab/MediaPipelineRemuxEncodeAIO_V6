import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDir, "..", "..", "..");
const require = createRequire(import.meta.url);

function resolveEslintEntry() {
  for (const candidate of [
    join(repoRoot, "node_modules", "eslint", "bin", "eslint.js"),
    join(repoRoot, "ops", "node_modules", "eslint", "bin", "eslint.js"),
  ]) {
    if (existsSync(candidate)) return candidate;
  }
  return join(dirname(require.resolve("eslint/package.json")), "bin", "eslint.js");
}

const result = spawnSync(process.execPath, [resolveEslintEntry(), ...process.argv.slice(2)], {
  cwd: repoRoot,
  env: process.env,
  stdio: "inherit",
});

if (result.error) throw result.error;
process.exit(result.status ?? 1);
