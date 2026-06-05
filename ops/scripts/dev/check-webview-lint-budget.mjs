import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { repoRelative, repoRoot, writeOrCheckJson } from "./webview-tooling-common.mjs";

const outputPath = "docs/generated/WEBVIEW_ESLINT_WARNING_BUDGET.json";
const targetGlob = "apps/desktop/webview/static/assets/**/*.js";
const require = createRequire(import.meta.url);

function parseArgs(argv) {
  return {
    check: argv.includes("--check"),
    write: argv.includes("--write") || !argv.includes("--check"),
  };
}

function runEslintJson() {
  const eslintEntry = resolveEslintEntry();
  const result = spawnSync(process.execPath, [eslintEntry, targetGlob, "--format", "json"], {
    cwd: repoRoot,
    encoding: "utf-8",
    maxBuffer: 64 * 1024 * 1024,
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.error) {
    throw result.error;
  }
  const stdout = result.stdout || "";
  if (!stdout.trim()) {
    if (result.stderr) console.error(result.stderr.trim());
    throw new Error(`ESLint did not return JSON output; exit code ${result.status}`);
  }
  return JSON.parse(stdout);
}

function resolveEslintEntry() {
  for (const candidate of [
    join(repoRoot, "node_modules", "eslint", "bin", "eslint.js"),
    join(repoRoot, "ops", "node_modules", "eslint", "bin", "eslint.js"),
  ]) {
    if (existsSync(candidate)) return candidate;
  }
  return join(dirname(require.resolve("eslint/package.json")), "bin", "eslint.js");
}

function summarize(results) {
  const byRule = {};
  const files = [];
  let totalWarnings = 0;
  let totalErrors = 0;

  for (const result of results) {
    const fileRules = {};
    for (const message of result.messages || []) {
      const rule = message.ruleId || "parse-error";
      fileRules[rule] = (fileRules[rule] || 0) + 1;
      if (message.severity === 2) totalErrors += 1;
      if (message.severity === 1) totalWarnings += 1;
      byRule[rule] = byRule[rule] || { warnings: 0, errors: 0 };
      if (message.severity === 2) byRule[rule].errors += 1;
      if (message.severity === 1) byRule[rule].warnings += 1;
    }
    const warningCount = result.warningCount || 0;
    const errorCount = result.errorCount || 0;
    if (warningCount || errorCount) {
      files.push({
        path: repoRelative(result.filePath),
        warnings: warningCount,
        errors: errorCount,
        rules: Object.fromEntries(Object.entries(fileRules).sort(([left], [right]) => left.localeCompare(right))),
      });
    }
  }

  return {
    schema_version: "webview_eslint_warning_budget.v1",
    generated_by: "ops/scripts/dev/check-webview-lint-budget.mjs",
    target: targetGlob,
    budget_policy: "Future checks fail on any ESLint error or on warning counts above this baseline by total or rule.",
    total_warnings: totalWarnings,
    total_errors: totalErrors,
    by_rule: Object.fromEntries(Object.entries(byRule).sort(([left], [right]) => left.localeCompare(right))),
    files: files.sort((left, right) => left.path.localeCompare(right.path)),
  };
}

function checkBudget(current) {
  const baselinePath = resolve(repoRoot, outputPath);
  if (!existsSync(baselinePath)) {
    console.error(`${outputPath} does not exist. Run npm run webview:lint:budget.`);
    return 1;
  }
  const baseline = JSON.parse(readFileSync(baselinePath, "utf-8"));
  const failures = [];
  if (current.total_errors > 0) {
    failures.push(`ESLint errors present: ${current.total_errors}`);
  }
  if (current.total_warnings > baseline.total_warnings) {
    failures.push(`warnings increased: ${current.total_warnings} > ${baseline.total_warnings}`);
  }
  const rules = new Set([...Object.keys(current.by_rule || {}), ...Object.keys(baseline.by_rule || {})]);
  for (const rule of [...rules].sort()) {
    const currentRule = current.by_rule?.[rule] || { warnings: 0, errors: 0 };
    const baselineRule = baseline.by_rule?.[rule] || { warnings: 0, errors: 0 };
    if (currentRule.errors > 0) failures.push(`${rule} errors present: ${currentRule.errors}`);
    if (currentRule.warnings > baselineRule.warnings) {
      failures.push(`${rule} warnings increased: ${currentRule.warnings} > ${baselineRule.warnings}`);
    }
  }
  if (failures.length) {
    console.error("ESLint warning budget failed:");
    failures.forEach((failure) => console.error(`- ${failure}`));
    return 1;
  }
  console.log(`ESLint warning budget ok: ${current.total_warnings}/${baseline.total_warnings} warnings, ${current.total_errors} errors.`);
  return 0;
}

const args = parseArgs(process.argv.slice(2));
const current = summarize(runEslintJson());
process.exitCode = args.check ? checkBudget(current) : writeOrCheckJson(outputPath, current, false);
