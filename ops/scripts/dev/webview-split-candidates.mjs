import { execFileSync } from "node:child_process";
import { join } from "node:path";
import {
  declarationName,
  isScriptLevelDeclaration,
  parseScript,
  readText,
  repoRoot,
  sortedUniq,
  traverse,
  writeOrCheckJson,
} from "./webview-tooling-common.mjs";

const outputPath = "docs/generated/WEBVIEW_SPLIT_CANDIDATES.json";
const analyzerPath = join(repoRoot, "ops", "scripts", "dev", "analyze-webview-godfiles.mjs");

const publicParentWrappers = {
  "apps/desktop/webview/static/assets/app.js": [
    "showPage",
    "refreshAll",
    "refreshAllNow",
    "renderDailyDriverReadiness",
    "renderHomeAtAGlance",
    "renderHomeAtAGlanceQueue",
    "externalDependencyRows",
    "externalDependencyOverallStatus",
    "externalDependencySummaryLines",
    "externalDependencyEvidenceText",
    "renderExternalDependencyDigest",
  ],
  "apps/desktop/webview/static/assets/settingsView.js": [
    "renderSettings",
    "initSettingsViewEvents",
    "validateCurrentSettings",
    "previewSettingsPatch",
    "saveSettingsPatch",
    "reloadSettingsFromDisk",
    "browseSettingsPath",
    "settingsPatchHasUnsavedChanges",
    "getLastSettings",
  ],
};

function parseArgs(argv) {
  return {
    check: argv.includes("--check"),
    write: argv.includes("--write") || !argv.includes("--check"),
  };
}

function analyzerJson() {
  const output = execFileSync(process.execPath, [analyzerPath, "--json"], {
    cwd: repoRoot,
    encoding: "utf-8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return JSON.parse(output);
}

function testsForCandidate(sourceFile, topic) {
  const tests = [
    "tests.webview.test_webview_frontend_mutation_boundary",
    "tests.webview.test_webview_inventory_docs",
  ];
  if (sourceFile.endsWith("/app.js")) {
    tests.push("tests.python.desktop.test_application_facade_web_static");
    if (topic.includes("layout") || topic.includes("home") || topic.includes("refresh")) {
      tests.push("tests.webview.test_webview_browser_layout_manager_smoke");
    }
  }
  if (sourceFile.endsWith("/settingsView.js")) {
    tests.push(
      "tests.python.desktop.test_application_facade_settings_workspace",
      "tests.webview.test_webview_settings_libraries",
      "tests.webview.test_webview_settings_patch_smoke"
    );
  }
  return [...new Set(tests)].sort();
}

function routeOwnershipNotes(sourceFile, routes) {
  if (!sourceFile.endsWith("/settingsView.js")) return [];
  const settingsRoutes = routes.filter((route) => route.startsWith("/api/settings/"));
  if (!settingsRoutes.length) return [];
  return settingsRoutes.map((route) => `${route} must remain settings-owned and backend-confirmed where applicable.`);
}

const knownGlobalIdentifiers = new Set([
  "AbortController",
  "Array",
  "Blob",
  "Boolean",
  "CSS",
  "CustomEvent",
  "Date",
  "Error",
  "Event",
  "File",
  "FileReader",
  "FormData",
  "Intl",
  "JSON",
  "Map",
  "Math",
  "MutationObserver",
  "Node",
  "Number",
  "Object",
  "Promise",
  "RegExp",
  "ResizeObserver",
  "Set",
  "String",
  "URL",
  "URLSearchParams",
  "WeakMap",
  "WeakSet",
  "clearInterval",
  "clearTimeout",
  "console",
  "document",
  "fetch",
  "history",
  "localStorage",
  "navigator",
  "requestAnimationFrame",
  "sessionStorage",
  "setInterval",
  "setTimeout",
  "undefined",
  "window",
]);

function isFunctionLikeVariable(path) {
  const init = path.node.declarations?.[0]?.init;
  return ["ArrowFunctionExpression", "FunctionExpression"].includes(init?.type);
}

function topLevelDeclarationMap(sourceFile) {
  const ast = parseScript(readText(sourceFile), sourceFile);
  const declarations = new Map();
  traverse(ast, {
    FunctionDeclaration(path) {
      if (!isScriptLevelDeclaration(path)) return;
      const name = declarationName(path);
      if (name) declarations.set(name, { name, path, kind: "function", line: path.node.loc?.start?.line || 1 });
    },
    VariableDeclaration(path) {
      if (!isScriptLevelDeclaration(path)) return;
      const name = declarationName(path);
      if (!name) return;
      declarations.set(name, {
        name,
        path,
        kind: isFunctionLikeVariable(path) ? "function" : path.node.kind,
        line: path.node.loc?.start?.line || 1,
      });
    },
  });
  return declarations;
}

function propertyName(node) {
  if (!node) return "";
  if (node.type === "Identifier") return node.name;
  if (node.type === "StringLiteral") return node.value;
  return "";
}

function skipIdentifier(path) {
  if (path.isBindingIdentifier()) return true;
  if (path.parentPath?.isMemberExpression({ property: path.node }) && !path.parent.computed) return true;
  if (path.parentPath?.isObjectProperty({ key: path.node }) && !path.parent.computed) return true;
  if (path.parentPath?.isObjectMethod({ key: path.node }) && !path.parent.computed) return true;
  if (path.parentPath?.isLabeledStatement()) return true;
  return false;
}

function identifierIsWrite(path) {
  const parent = path.parentPath;
  if (!parent) return false;
  if (parent.isUpdateExpression()) return true;
  if (parent.isAssignmentExpression() && parent.node.left === path.node) return true;
  if ((parent.isForInStatement() || parent.isForOfStatement()) && parent.node.left === path.node) return true;
  if (parent.isAssignmentPattern() && parent.node.left === path.node) return true;
  return false;
}

function classifyCandidateDependencies(sourceFile, candidate) {
  const declarations = topLevelDeclarationMap(sourceFile);
  const candidateNames = new Set(candidate.declarations);
  const parentStateReads = [];
  const parentStateWrites = [];
  const outsideLocalFunctions = [];
  const windowDependencies = [];
  const browserGlobals = [];
  const unresolvedGlobals = [];

  for (const name of candidate.declarations) {
    const declaration = declarations.get(name);
    if (!declaration) continue;
    declaration.path.traverse({
      MemberExpression(path) {
        if (path.node.object?.type !== "Identifier" || path.node.object.name !== "window") return;
        const property = propertyName(path.node.property);
        if (property) windowDependencies.push(`window.${property}`);
      },
      Identifier(path) {
        if (skipIdentifier(path)) return;
        const name = path.node.name;
        const binding = path.scope.getBinding(name);
        if (!binding) {
          if (knownGlobalIdentifiers.has(name)) {
            browserGlobals.push(name);
          } else {
            unresolvedGlobals.push(name);
          }
          return;
        }
        const dependency = declarations.get(binding.identifier.name);
        if (!dependency || candidateNames.has(dependency.name)) return;
        if (dependency.kind === "function") {
          outsideLocalFunctions.push(dependency.name);
        } else if (identifierIsWrite(path)) {
          parentStateWrites.push(dependency.name);
        } else {
          parentStateReads.push(dependency.name);
        }
      },
    });
  }

  const unique = {
    parent_state_reads: sortedUniq(parentStateReads),
    parent_state_writes: sortedUniq(parentStateWrites),
    outside_local_functions: sortedUniq(outsideLocalFunctions),
    dom_dependencies: sortedUniq(candidate.domIds),
    api_dependencies: sortedUniq(candidate.apiRoutes),
    window_dependencies: sortedUniq(windowDependencies),
    browser_globals: sortedUniq(browserGlobals),
    unresolved_global_dependencies: sortedUniq(unresolvedGlobals),
  };
  const reasons = [];
  if (unique.parent_state_writes.length) reasons.push("writes parent-owned top-level state");
  if (unique.parent_state_reads.length > 6) reasons.push("reads several parent-owned top-level state values");
  if (unique.outside_local_functions.length > 8) reasons.push("depends on several parent/local helper functions");
  if (unique.unresolved_global_dependencies.length) reasons.push("uses unresolved ordered-script globals");
  if (candidate.apiRoutes.some((route) => route.startsWith("/api/settings/"))) reasons.push("touches settings-owned backend routes");

  let movement = "safe_to_move_now";
  if (reasons.length) movement = "needs_wrapper_or_context";
  if (candidate.apiRoutes.some((route) => ["/api/settings/save-patch", "/api/schedule/save"].includes(route))) {
    movement = "needs_manual_review";
    reasons.push("touches confirmation-gated persistence route");
  }
  unique.movement_assessment = movement;
  unique.assessment_reasons = sortedUniq(reasons);
  return unique;
}

function buildManifest() {
  const analyses = analyzerJson();
  const sources = analyses.map((analysis) => {
    const globalsToPreserve = [
      ...analysis.namespaceExports,
      ...analysis.flatExports,
    ].sort();
    const wrapperNames = publicParentWrappers[analysis.path] || [];
    return {
      source_file: analysis.path,
      globals_to_preserve: globalsToPreserve,
      candidate_count: analysis.candidates.length,
      candidates: analysis.candidates.map((candidate) => ({
        source_file: analysis.path,
        proposed_child_file: candidate.suggestedFile,
        topic: candidate.topic,
        line_range: {
          start: candidate.startLine,
          end: candidate.endLine,
          line_count: candidate.lineCount,
        },
        functions_to_move: candidate.declarations,
        parent_wrappers_required: candidate.declarations.filter((name) => wrapperNames.includes(name)),
        dependencies_to_resolve: candidate.dependsOnLocalOutsideSlice,
        globals_to_preserve: globalsToPreserve,
        api_routes: candidate.apiRoutes,
        dom_ids_touched: candidate.domIds,
        event_types: candidate.events,
        dependency_classification: classifyCandidateDependencies(analysis.path, candidate),
        route_ownership_notes: routeOwnershipNotes(analysis.path, candidate.apiRoutes),
        tests_affected: testsForCandidate(analysis.path, candidate.topic),
      })),
    };
  });

  return {
    schema_version: "webview_split_candidates.v1",
    generated_by: "ops/scripts/dev/webview-split-candidates.mjs",
    source_analyzer: "ops/scripts/dev/analyze-webview-godfiles.mjs",
    no_slicing_note: "This manifest is prework only. It identifies future split candidates but does not create, delete, or rewrite WebView assets.",
    split_rules: [
      "Keep the plain ordered <script> runtime model.",
      "Load child assets before their parent file.",
      "Keep public globals and compatibility wrappers until tests prove they are unused.",
      "Do not move settings persistence commands out of settingsView.js until route ownership tests are updated deliberately.",
    ],
    sources,
  };
}

const args = parseArgs(process.argv.slice(2));
process.exitCode = writeOrCheckJson(outputPath, buildManifest(), args.check);
