import { readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = process.cwd();
const assetsRoot = join(repoRoot, "DesktopApp", "mediapipeline_desktop_app", "ui_web", "static", "assets");

function collectJsFiles(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectJsFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".js")) {
      files.push(fullPath);
    }
  }
  return files.sort();
}

let failed = false;
for (const file of collectJsFiles(assetsRoot)) {
  const result = spawnSync(process.execPath, ["--check", file], {
    encoding: "utf-8",
    stdio: "pipe",
  });
  const displayPath = relative(repoRoot, file).replaceAll("\\", "/");
  if (result.status === 0) {
    console.log(`ok ${displayPath}`);
    continue;
  }
  failed = true;
  console.error(`failed ${displayPath}`);
  if (result.stdout) console.error(result.stdout.trim());
  if (result.stderr) console.error(result.stderr.trim());
}

process.exit(failed ? 1 : 0);
