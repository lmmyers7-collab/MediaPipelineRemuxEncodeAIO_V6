import {
  analyzeScriptAsset,
  collectScriptTags,
  readText,
  repoRelative,
  scriptSrcToRepoPath,
  webviewIndexPath,
  writeOrCheckJson,
} from "./webview-tooling-common.mjs";

const outputPath = "docs/generated/WEBVIEW_ROUTE_OWNERSHIP_GUARD.json";

const confirmationRules = [
  {
    route: "/api/settings/save-patch",
    confirmation: "confirm_save",
    pattern: /confirm_save\s*:\s*true/,
    note: "Settings persistence must remain explicitly backend-confirmed.",
  },
  {
    route: "/api/schedule/save",
    confirmation: "confirm_save",
    pattern: /confirm_save\s*:\s*true/,
    note: "Schedule persistence must remain explicitly backend-confirmed.",
  },
  {
    route: "/api/failures/clear",
    confirmation: "confirm_clear",
    pattern: /confirm_clear\s*:/,
    note: "Failure clear is destructive state mutation and must remain confirmed.",
  },
  {
    route: "/api/final-library-promotion/promote-queue",
    confirmation: "confirm_promote",
    pattern: /confirm_promote\s*:\s*true/,
    note: "Final-library promotion must remain explicitly backend-confirmed.",
  },
  {
    route: "/api/rename/filter-cases",
    confirmation: "confirm_append",
    pattern: /confirm_append\s*:\s*true/,
    note: "Rename filter corpus writes must remain explicitly backend-confirmed.",
  },
];

const settingsReadRoutesAllowedOutsideSettingsAssets = new Set([
  "/api/settings/workspace",
]);

function parseArgs(argv) {
  return {
    check: argv.includes("--check"),
    write: argv.includes("--write") || !argv.includes("--check"),
  };
}

function settingsOwned(path) {
  const fileName = path.split("/").pop() || "";
  return fileName.startsWith("settings");
}

function routeOwners(scripts) {
  const owners = new Map();
  for (const script of scripts) {
    for (const route of script.api_routes) {
      if (!owners.has(route)) owners.set(route, []);
      owners.get(route).push(script.path);
    }
  }
  return [...owners.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([route, files]) => ({ route, files: files.sort() }));
}

function confirmationEvidence(rule, scripts) {
  const files = scripts
    .filter((script) => script.source.includes(rule.route))
    .map((script) => ({
      path: script.path,
      has_confirmation: rule.pattern.test(script.source),
    }));
  return {
    ...rule,
    files,
    ok: files.length > 0 && files.every((file) => file.has_confirmation),
  };
}

function buildReport() {
  const indexHtml = readText(repoRelative(webviewIndexPath));
  const scripts = collectScriptTags(indexHtml)
    .map((src) => ({ src, path: scriptSrcToRepoPath(src) }))
    .filter((item) => item.path)
    .map((item) => {
      const analysis = analyzeScriptAsset(item.path);
      return {
        ...item,
        source: readText(item.path),
        api_routes: analysis.api_routes,
      };
    });
  const owners = routeOwners(scripts);
  const violations = [];

  owners
    .filter((owner) => owner.route.startsWith("/api/settings/") && !settingsReadRoutesAllowedOutsideSettingsAssets.has(owner.route))
    .forEach((owner) => {
      const badFiles = owner.files.filter((path) => !settingsOwned(path));
      if (badFiles.length) {
        violations.push({
          rule: "settings-route-owner",
          route: owner.route,
          files: badFiles,
          message: "/api/settings/* routes must stay in settings-owned WebView assets.",
        });
      }
    });

  const confirmation = confirmationRules.map((rule) => confirmationEvidence(rule, scripts));
  confirmation
    .filter((rule) => !rule.ok)
    .forEach((rule) => {
      violations.push({
        rule: "confirmation-required",
        route: rule.route,
        files: rule.files.map((file) => file.path),
        message: `${rule.route} must include ${rule.confirmation}: true where posted.`,
      });
    });

  return {
    schema_version: "webview_route_ownership_guard.v1",
    generated_by: "ops/scripts/dev/check-webview-route-ownership.mjs",
    source_index: repoRelative(webviewIndexPath),
    guard_note: "Pre-split guard. Settings routes must remain settings-owned, and listed mutation routes must keep explicit backend confirmation.",
    ok: violations.length === 0,
    violations,
    route_owners: owners,
    confirmation_rules: confirmation,
  };
}

const args = parseArgs(process.argv.slice(2));
const report = buildReport();
const staleOrWriteExit = writeOrCheckJson(outputPath, report, args.check);
if (args.check && report.violations.length) {
  report.violations.forEach((violation) => console.error(`${violation.rule}: ${violation.message}`));
  process.exitCode = 1;
} else {
  process.exitCode = staleOrWriteExit;
}
