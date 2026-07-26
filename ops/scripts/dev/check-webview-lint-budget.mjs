import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { repoRelative, repoRoot, writeOrCheckJson } from "./webview-tooling-common.mjs";

const outputPath = "docs/generated/WEBVIEW_ESLINT_WARNING_BUDGET.json";
const targetGlob = "apps/desktop/webview/static/assets/**/*.js";
const schemaVersion = "webview_eslint_warning_budget.v2";
const legacySchemaVersion = "webview_eslint_warning_budget.v1";
const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const requestedModes = [
    argv.includes("--check") ? "check" : "",
    argv.includes("--write") ? "write" : "",
    argv.includes("--ratchet-no-undef") ? "ratchet" : "",
  ].filter(Boolean);
  if (requestedModes.length > 1) {
    throw new Error("Choose exactly one lint-budget mode: --check, --write, or --ratchet-no-undef.");
  }
  return { mode: requestedModes[0] || "write" };
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

function noUndefIdentifier(message, path) {
  const match = String(message || "").match(/^'([^']+)' is not defined\.$/);
  if (!match) {
    throw new Error(`Malformed no-undef message in ${path}: ${JSON.stringify(message)}`);
  }
  return match[1];
}

export function summarize(results) {
  const byRule = {};
  const noUndefCounts = new Map();
  const files = [];
  let totalWarnings = 0;
  let totalErrors = 0;

  for (const result of results) {
    const path = repoRelative(result.filePath);
    const fileRules = {};
    for (const message of result.messages || []) {
      const rule = message.ruleId || "parse-error";
      fileRules[rule] = (fileRules[rule] || 0) + 1;
      if (message.severity === 2) totalErrors += 1;
      if (message.severity === 1) totalWarnings += 1;
      byRule[rule] = byRule[rule] || { warnings: 0, errors: 0 };
      if (message.severity === 2) byRule[rule].errors += 1;
      if (message.severity === 1) byRule[rule].warnings += 1;
      if (rule === "no-undef") {
        const identifier = noUndefIdentifier(message.message, path);
        const key = JSON.stringify([path, identifier]);
        noUndefCounts.set(key, (noUndefCounts.get(key) || 0) + 1);
      }
    }
    const warningCount = result.warningCount || 0;
    const errorCount = result.errorCount || 0;
    if (warningCount || errorCount) {
      files.push({
        path,
        warnings: warningCount,
        errors: errorCount,
        rules: Object.fromEntries(Object.entries(fileRules).sort(([left], [right]) => left.localeCompare(right))),
      });
    }
  }

  const noUndefPairs = [...noUndefCounts.entries()]
    .map(([key, warnings]) => {
      const [path, identifier] = JSON.parse(key);
      return { path, identifier, warnings };
    })
    .sort((left, right) => left.path.localeCompare(right.path) || left.identifier.localeCompare(right.identifier));

  return {
    schema_version: schemaVersion,
    generated_by: "ops/scripts/dev/check-webview-lint-budget.mjs",
    target: targetGlob,
    budget_policy: (
      "Future checks fail on ESLint errors, warning increases by total/rule/file, or any no-undef pair drift. "
      + "No-undef decreases must be accepted with the dedicated ratchet command."
    ),
    total_warnings: totalWarnings,
    total_errors: totalErrors,
    by_rule: Object.fromEntries(Object.entries(byRule).sort(([left], [right]) => left.localeCompare(right))),
    no_undef_pairs: noUndefPairs,
    files: files.sort((left, right) => left.path.localeCompare(right.path)),
  };
}

function pairCounts(summary) {
  const counts = new Map();
  if (!Array.isArray(summary.no_undef_pairs)) {
    throw new Error("Malformed v2 lint budget: no_undef_pairs must be an array.");
  }
  for (const entry of summary.no_undef_pairs) {
    const path = typeof entry?.path === "string" ? entry.path : "";
    const identifier = typeof entry?.identifier === "string" ? entry.identifier : "";
    const warnings = entry?.warnings;
    if (!path || !identifier || !Number.isInteger(warnings) || warnings < 1) {
      throw new Error(`Malformed no_undef_pairs entry: ${JSON.stringify(entry)}`);
    }
    const key = JSON.stringify([path, identifier]);
    if (counts.has(key)) {
      throw new Error(`Duplicate no_undef_pairs entry: ${path} :: ${identifier}`);
    }
    counts.set(key, warnings);
  }
  return counts;
}

export function compareNoUndefPairs(current, baseline) {
  const currentCounts = pairCounts(current);
  const baselineCounts = pairCounts(baseline);
  const keys = new Set([...currentCounts.keys(), ...baselineCounts.keys()]);
  const drift = { increased: [], decreased: [] };
  for (const key of [...keys].sort()) {
    const [path, identifier] = JSON.parse(key);
    const currentCount = currentCounts.get(key) || 0;
    const baselineCount = baselineCounts.get(key) || 0;
    const entry = { path, identifier, current: currentCount, baseline: baselineCount };
    if (currentCount > baselineCount) drift.increased.push(entry);
    if (currentCount < baselineCount) drift.decreased.push(entry);
  }
  return drift;
}

function ruleWarnings(summary, rule) {
  return summary.by_rule?.[rule]?.warnings || 0;
}

function pairDescription(entry) {
  return `${entry.path} :: ${entry.identifier} (${entry.current} > ${entry.baseline})`;
}

export function noUndefRatchetFailures(current, baseline, mode) {
  if (!["check", "write", "ratchet"].includes(mode)) {
    throw new Error(`Unknown no-undef ratchet mode: ${mode}`);
  }
  if (baseline.schema_version === legacySchemaVersion) {
    const currentCount = ruleWarnings(current, "no-undef");
    const baselineCount = ruleWarnings(baseline, "no-undef");
    if (currentCount > baselineCount) {
      return [`no-undef warnings increased during v2 migration: ${currentCount} > ${baselineCount}`];
    }
    if (mode !== "ratchet") {
      return ["no-undef baseline is v1; migrate it with npm run webview:lint:no-undef:ratchet"];
    }
    return [];
  }
  if (baseline.schema_version !== schemaVersion) {
    return [`unsupported ESLint warning budget schema: ${JSON.stringify(baseline.schema_version)}`];
  }
  const drift = compareNoUndefPairs(current, baseline);
  const failures = drift.increased.map((entry) => `no-undef pair increased: ${pairDescription(entry)}`);
  if (drift.decreased.length && mode !== "ratchet") {
    const details = drift.decreased
      .map((entry) => `${entry.path} :: ${entry.identifier} (${entry.current} < ${entry.baseline})`)
      .join(", ");
    failures.push(`no-undef warnings decreased; ratchet the exact baseline with npm run webview:lint:no-undef:ratchet: ${details}`);
  }
  return failures;
}

function fileRuleCounts(summary) {
  const counts = new Map();
  for (const file of summary.files || []) {
    for (const [rule, count] of Object.entries(file.rules || {})) {
      counts.set(JSON.stringify([file.path, rule]), count);
    }
  }
  return counts;
}

export function budgetFailures(current, baseline, mode = "check") {
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
  const currentFileRules = fileRuleCounts(current);
  const baselineFileRules = fileRuleCounts(baseline);
  for (const [key, currentCount] of [...currentFileRules.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    const baselineCount = baselineFileRules.get(key) || 0;
    if (currentCount > baselineCount) {
      const [path, rule] = JSON.parse(key);
      failures.push(`${path} ${rule} warnings increased: ${currentCount} > ${baselineCount}`);
    }
  }
  failures.push(...noUndefRatchetFailures(current, baseline, mode));
  return failures;
}

function readBaseline() {
  const baselinePath = resolve(repoRoot, outputPath);
  if (!existsSync(baselinePath)) {
    throw new Error(`${outputPath} does not exist; restore it before changing the lint budget.`);
  }
  return JSON.parse(readFileSync(baselinePath, "utf-8"));
}

function reportFailures(failures) {
  console.error("ESLint warning budget failed:");
  failures.forEach((failure) => console.error(`- ${failure}`));
  return 1;
}

function checkOrWriteBudget(current, mode) {
  const baseline = readBaseline();
  const failures = budgetFailures(current, baseline, mode);
  if (failures.length) return reportFailures(failures);
  if (mode === "check") {
    console.log(`ESLint warning budget ok: ${current.total_warnings}/${baseline.total_warnings} warnings, ${current.total_errors} errors.`);
    return 0;
  }
  return writeOrCheckJson(outputPath, current, false);
}

function isMainModule() {
  return Boolean(process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href);
}

if (isMainModule()) {
  try {
    const args = parseArgs(process.argv.slice(2));
    const current = summarize(runEslintJson());
    process.exitCode = checkOrWriteBudget(current, args.mode);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
