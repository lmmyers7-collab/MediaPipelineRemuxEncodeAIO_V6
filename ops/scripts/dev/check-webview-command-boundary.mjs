import {
  analyzeScriptAsset,
  collectScriptTags,
  parseScript,
  readText,
  repoRelative,
  scriptSrcToRepoPath,
  traverse,
  webviewIndexPath,
  webviewStaticRoot,
  writeOrCheckJson,
} from "./webview-tooling-common.mjs";

const outputPath = "docs/generated/WEBVIEW_COMMAND_BOUNDARY_AUDIT.json";
const contractFiles = [
  "src/mediapipeline/desktop/api/contract_read.py",
  "src/mediapipeline/desktop/api/contract_command.py",
];

const highRiskEffects = new Set([
  "app-state-write",
  "audit-state-write",
  "backend-lifecycle",
  "completed-manifest-write",
  "completed-sidecar-json-write",
  "config-write",
  "control-flag-write",
  "control-state-write",
  "deployment-write",
  "diagnostic-process",
  "failure-marker-write",
  "filesystem-mutation",
  "metrics-backfill-state-write",
  "metrics-state-write",
  "process-dry-run",
  "process-launch",
  "pending-manifest-write",
  "pending-orphan-manifest-write",
  "queue-state-write",
  "report-file-write",
  "secret-transfer",
  "test-fixture-write",
  "tooling-artifact-write",
  "ui-state-write",
  "validation-log-write",
]);

const routeOwnerRules = [
  { route: /^\/api\/queue\//, owners: ["Queue"] },
  { route: /^\/api\/completed(?:$|\/|\?)/, owners: ["Completed"] },
  { route: /^\/api\/publish-reconciliation(?:$|\?)/, owners: ["Completed"] },
  { route: /^\/api\/final-library-promotion\//, owners: ["Completed"] },
  { route: /^\/api\/pending-publish\//, owners: ["Pending Publish"] },
  { route: /^\/api\/rename\//, owners: ["Rename", "Settings"] },
  { route: /^\/api\/settings\//, owners: ["Settings", "Settings Wizard", "Network"] },
  { route: /^\/api\/schedule\//, owners: ["Schedule"] },
  { route: /^\/api\/sample-validation\//, owners: ["Home", "Cross Page"] },
  { route: /^\/api\/diagnostics\//, owners: ["Diagnostics"] },
  { route: /^\/api\/maintenance\/archive-state-journals$/, owners: ["Launch", "Maintenance"] },
  { route: /^\/api\/maintenance\//, owners: ["Maintenance"] },
  { route: /^\/api\/maintenance$/, owners: ["Maintenance"] },
  { route: /^\/api\/metrics\//, owners: ["Metrics"] },
  { route: /^\/api\/metrics$/, owners: ["Metrics"] },
  { route: /^\/api\/network\//, owners: ["Network"] },
  { route: /^\/api\/pipeline\//, owners: ["Launch", "App Shell"] },
  { route: /^\/api\/audit\//, owners: ["Launch", "Reports"] },
  { route: /^\/api\/rerun\//, owners: ["Launch", "Reports"] },
  { route: /^\/api\/backend\//, owners: ["App Shell", "Diagnostics"] },
  { route: /^\/api\/ui-preferences$/, owners: ["App Shell"] },
  { route: /^\/api\/libraries\//, owners: ["Libraries", "Settings"] },
  { route: /^\/api\/watch-folders\//, owners: ["Schedule"] },
  { route: /^\/api\/subtitle-qa\//, owners: ["Queue", "Completed"] },
  { route: /^\/api\/failures(?:$|\/)/, owners: ["Reports"] },
];

const confirmationRules = [
  { route: "/api/settings/save-patch", confirmation: "confirm_save", pattern: /confirm_save\s*:\s*true/ },
  { route: "/api/settings/wizard/save", confirmation: "confirm_save", pattern: /confirm_save\s*:\s*true/ },
  { route: "/api/schedule/save", confirmation: "confirm_save", pattern: /confirm_save\s*:\s*true/ },
  { route: "/api/failures/clear", confirmation: "confirm_clear", pattern: /confirm_clear\s*:/ },
  { route: "/api/final-library-promotion/promote-queue", confirmation: "confirm_promote", pattern: /confirm_promote\s*:\s*true/ },
  { route: "/api/rename/apply", confirmation: "confirm_apply", pattern: /confirm_apply\s*=\s*true|confirm_apply\s*:\s*true/ },
  { route: "/api/rename/filter-cases", confirmation: "confirm_append", pattern: /confirm_append\s*:\s*true/ },
  { route: "/api/queue/file-overrides/series-apply", confirmation: "confirm_apply", pattern: /confirm_apply\s*:\s*true/ },
  {
    route: "/api/network/coordinator/join-blob",
    confirmation: "confirm_create",
    pattern: /confirm_create\s*:\s*true/,
    evidenceFiles: ["apps/desktop/webview/static/assets/networkView.js"],
  },
  {
    route: "/api/network/worker/join-cluster",
    confirmation: "confirm_import",
    pattern: /confirm_import\s*:\s*true/,
    evidenceFiles: ["apps/desktop/webview/static/assets/networkView.js"],
  },
];

const selectorRouteRules = [
  { route: "/api/queue/open", required: ["row_key", "target"], forbidden: ["path", "source_path", "output_path", "local_file"] },
  { route: "/api/completed/open", required: ["row_key", "target"], forbidden: ["path", "source_path", "output_path", "local_file"] },
  { route: "/api/pending-publish/open", required: ["row_key", "target"], forbidden: ["path", "source_path", "output_path", "local_file"] },
  { route: "/api/diagnostics/open", required: ["target"], forbidden: ["path", "source_path", "output_path", "local_file"] },
  { route: "/api/diagnostics/tdarr-matrix/evidence/open", required: ["run_id", "target"], forbidden: ["path", "source_path", "output_path", "local_file"] },
  { route: "/api/maintenance/dependency-atlas/open-folder", required: [], forbidden: ["path", "source_path", "output_path", "local_file"] },
];

const directMutationApiRules = [
  { label: "direct fetch outside apiClient", pattern: /\bfetch\s*\(/, allowed: ["apps/desktop/webview/static/assets/apiClient.js"] },
  { label: "direct Tauri bridge access", pattern: /window\.__TAURI__|\b__TAURI__\b/, allowed: ["apps/desktop/webview/static/assets/tauriLifecycleBridge.js"] },
  { label: "Tauri invoke", pattern: /\binvoke\s*\(|\.invoke\s*\(/, allowed: [] },
  { label: "Tauri shell/fs/process capability", pattern: /\b(writeTextFile|writeFile|removeFile|removeDir|renameFile|Command|openPath|openUrl)\s*\(/, allowed: [] },
  { label: "Node filesystem/process import", pattern: /\b(require|import)\s*\(\s*["'](?:fs|node:fs|child_process|node:child_process)["']|from\s+["'](?:fs|node:fs|child_process|node:child_process)["']/, allowed: [] },
  { label: "direct filesystem path mutation wording", pattern: /\b(unlink|rm|rmdir|rename|moveFile|copyFile)\s*\(/, allowed: [] },
];

const highRiskControlTerms = [
  "append",
  "apply",
  "archive",
  "backfill",
  "build",
  "clear",
  "delete",
  "drain",
  "export",
  "force",
  "import",
  "kill",
  "pause",
  "promote",
  "reload",
  "repair",
  "rerun",
  "reset",
  "resume",
  "run",
  "save",
  "scan",
  "shutdown",
  "start",
  "stop",
];

const localControlRules = [
  { pattern: /\bnav-button\b|data-page=|data-cross-page-target=/, classification: "local-navigation" },
  { pattern: /data-\w+-tab=|role=["']tab["']|settings-section-nav-btn|data-wizard-step-button=/, classification: "local-tab-navigation" },
  { pattern: /filter|search|column-mode|sort|show|hide|toggle|advanced|evidence|theme|layout-editor|customize-layout|reset-layout/, classification: "local-display-state" },
  { pattern: /copy|clipboard|diagnostic summary/i, classification: "local-copy" },
  { pattern: /settings-.*-(apply|reset)-button|settings-builder-|settings-video-|settings-quality-|settings-file-safety-|settings-pending-|settings-subtitle-|settings-audio-|settings-queue-|settings-runtime-|settings-rename-cleaning-filters/, classification: "local-settings-staging" },
  { pattern: /settings-library-/, classification: "local-settings-staging" },
  { pattern: /rename-(bulk|clear|check|move|natural|use-|add-path|save-override|clear-override|log-case-open|log-case-cancel)/, classification: "local-rename-staging" },
  { pattern: /queue-manual-save-order|save loaded backend order/i, classification: "local-queue-order-staging" },
  { pattern: /sample-validation-.*clear|sample-validation-clear/, classification: "local-sample-validation-staging" },
  { pattern: /data-launch-mode=|pipeline-single-file-clear|single file|backend queue|validate|continuous|run once/i, classification: "local-launch-intent-staging" },
  { pattern: /schedule-editor-(load|clear|allow)/, classification: "local-schedule-staging" },
  { pattern: /settings-deployment-|settings-open-wizard|settings-wizard-(back|next|add-library|copy-diagnostics)/, classification: "local-guided-setup" },
  { pattern: /network-lifecycle-confirm-cancel|role-setup-cancel|settings-network-(apply|reset|path-map-add-row)/, classification: "local-network-staging" },
  { pattern: /data-network-future-control=/, classification: "disabled-future-network-control" },
  { pattern: /load-latest|compare|refresh|read tail|read-tail|view|detail|select|rows?/, classification: "local-read-navigation" },
];

const routeHintRules = [
  { pattern: /backend-shutdown-button/, route: "/api/backend/shutdown" },
  { pattern: /data-control-action=|pipeline-control|force stop/i, route: "/api/pipeline/control" },
  { pattern: /pipeline-start-button|pipeline start|start pipeline/i, route: "/api/pipeline/start" },
  { pattern: /pending-drain-button|publish parked|drain/i, route: "/api/pipeline/start" },
  { pattern: /audit-start-button|start audit/i, route: "/api/audit/start" },
  { pattern: /rerun-start-button|rerun start|start rerun/i, route: "/api/rerun/start" },
  { pattern: /queue-scan|scan sources/i, route: "/api/queue/scan" },
  { pattern: /queue-priority|priority/i, route: "/api/queue/priority" },
  { pattern: /queue-strategy|strategy/i, route: "/api/queue/strategy" },
  { pattern: /fo-.*(save|clear)|file-overrides.*(save|clear)/i, route: "/api/queue/file-overrides" },
  { pattern: /series-preview/i, route: "/api/queue/file-overrides/series-preview" },
  { pattern: /series-apply/i, route: "/api/queue/file-overrides/series-apply" },
  { pattern: /route-preview/i, route: "/api/queue/file-overrides/route-preview" },
  { pattern: /final-library-promote|promote selected|promote reviewed/i, route: "/api/final-library-promotion/promote-queue" },
  { pattern: /final-library-pause|pause promotion/i, route: "/api/final-library-promotion/pause" },
  { pattern: /final-library-resume|resume promotion/i, route: "/api/final-library-promotion/resume" },
  { pattern: /pending-recovery-plan/i, route: "/api/pending-publish/recovery-plan" },
  { pattern: /completed-reconcile-manifest-dry-run-button/i, route: "/api/completed/reconcile-manifest-dry-run" },
  { pattern: /completed-reconcile-manifest-apply-button/i, route: "/api/completed/reconcile-manifest" },
  { pattern: /completed-repair-sidecar-dry-run-button/i, route: "/api/completed/repair-sidecar-metadata-dry-run" },
  { pattern: /completed-repair-sidecar-apply-button/i, route: "/api/completed/repair-sidecar-metadata" },
  { pattern: /pending-repair-manifest-dry-run-button/i, route: "/api/pending-publish/repair-manifest-dry-run" },
  { pattern: /pending-repair-manifest-apply-button/i, route: "/api/pending-publish/repair-manifest" },
  { pattern: /pending-reconcile-orphan-dry-run-button/i, route: "/api/pending-publish/reconcile-orphan-payloads-dry-run" },
  { pattern: /pending-reconcile-orphan-apply-button/i, route: "/api/pending-publish/reconcile-orphan-payloads" },
  { pattern: /data-open-diagnostics=|diagnostics-open|open diagnostics/i, route: "/api/diagnostics/open" },
  { pattern: /tdarr-matrix-audit-action/i, route: "/api/diagnostics/tdarr-matrix-audit" },
  { pattern: /tdarr-matrix-audit-rerun/i, route: "/api/diagnostics/tdarr-matrix/rerun" },
  { pattern: /release-dry-run/i, route: "/api/maintenance/release-dry-run" },
  { pattern: /release-build/i, route: "/api/maintenance/release-build" },
  { pattern: /backfill-dry-run/i, route: "/api/maintenance/completed-backfill-dry-run" },
  { pattern: /dependency-atlas-open/i, route: "/api/maintenance/dependency-atlas/open-folder" },
  { pattern: /dependency-atlas/i, route: "/api/maintenance/dependency-atlas" },
  { pattern: /rename-preview|test filename/i, route: "/api/rename/preview" },
  { pattern: /rename-browse|browse files|browse folder/i, route: "/api/rename/browse" },
  { pattern: /rename-apply/i, route: "/api/rename/apply" },
  { pattern: /rename-log-case|append filter case/i, route: "/api/rename/filter-cases" },
  { pattern: /settings-wizard-validate-paths/i, route: "/api/settings/wizard/validate-paths" },
  { pattern: /settings-wizard-detect-tools/i, route: "/api/settings/wizard/validate-tools" },
  { pattern: /settings-wizard-probe-hardware/i, route: "/api/settings/wizard/probe-hardware" },
  { pattern: /settings-wizard-validate-workers/i, route: "/api/settings/wizard/validate-workers" },
  { pattern: /settings-wizard-preview/i, route: "/api/settings/wizard/preview" },
  { pattern: /settings-wizard-save/i, route: "/api/settings/wizard/save" },
  { pattern: /settings-.*browse|settings-path-browse/i, route: "/api/settings/browse-path" },
  { pattern: /settings-validate/i, route: "/api/settings/validate" },
  { pattern: /settings-preview|preview patch/i, route: "/api/settings/preview-patch" },
  { pattern: /settings-save|save settings/i, route: "/api/settings/save-patch" },
  { pattern: /settings-reload|reload from disk/i, route: "/api/settings/reload" },
  { pattern: /schedule-editor-preview/i, route: "/api/schedule/preview" },
  { pattern: /schedule-editor-save|save schedule/i, route: "/api/schedule/save" },
  { pattern: /sample-validation-preview/i, route: "/api/sample-validation/preview" },
  { pattern: /sample-validation-append|append validation/i, route: "/api/sample-validation/append" },
  { pattern: /network-lifecycle|data-network-lifecycle/i, route: "contract:/api/network/* lifecycle" },
  { pattern: /network-worker-test|test connection/i, route: "/api/network/worker/test-connection" },
  { pattern: /discover-coordinator/i, route: "/api/network/worker/discover-coordinators" },
  { pattern: /join-blob/i, route: "/api/network/coordinator/join-blob" },
  { pattern: /join-cluster|join cluster|import join/i, route: "/api/network/worker/join-cluster" },
  { pattern: /metrics-backfill|backfill enabled/i, route: "/api/metrics/backfill" },
  { pattern: /metrics-source|metric.*source/i, route: "/api/metrics/sources" },
  { pattern: /failure.*clear|clear failures|clear markers/i, route: "/api/failures/clear" },
  { pattern: /fo-remux-pilot-promote/i, route: "/api/queue/file-overrides/remux-pilot-promote" },
  { pattern: /audit.*score|score-policy/i, route: "/api/audit/score-policy" },
  { pattern: /audit.*ignore|ignore/i, route: "/api/audit/ignore" },
  { pattern: /export.*csv|export-rerun/i, route: "/api/audit/export-rerun-csv" },
];

function parseArgs(argv) {
  return {
    check: argv.includes("--check"),
    write: argv.includes("--write") || !argv.includes("--check"),
  };
}

function normalizeRoute(route) {
  return String(route || "").split("?")[0];
}

function memberName(node) {
  if (!node) return "";
  if (node.type === "Identifier") return node.name;
  if (node.type === "StringLiteral") return node.value;
  return "";
}

function stringLiteralValue(node) {
  if (node?.type === "StringLiteral") return node.value;
  if (node?.type === "TemplateLiteral" && node.expressions.length === 0) return node.quasis[0]?.value?.cooked || "";
  return "";
}

function callName(node) {
  const callee = node?.callee;
  if (callee?.type === "Identifier") return callee.name;
  if (callee?.type === "MemberExpression") return memberName(callee.property);
  return "";
}

function extractObjectBlocks(source) {
  const blocks = [];
  let index = 0;
  while (index < source.length) {
    const start = source.indexOf("{", index);
    if (start === -1) break;
    let depth = 0;
    let inString = "";
    let escape = false;
    for (let cursor = start; cursor < source.length; cursor += 1) {
      const char = source[cursor];
      if (inString) {
        if (escape) {
          escape = false;
        } else if (char === "\\") {
          escape = true;
        } else if (char === inString) {
          inString = "";
        }
        continue;
      }
      if (char === "\"" || char === "'") {
        inString = char;
        continue;
      }
      if (char === "{") depth += 1;
      if (char === "}") {
        depth -= 1;
        if (depth === 0) {
          blocks.push(source.slice(start, cursor + 1));
          index = cursor + 1;
          break;
        }
      }
    }
    if (index <= start) index = start + 1;
  }
  return blocks;
}

function extractStringField(block, field) {
  const match = block.match(new RegExp(`"${field}"\\s*:\\s*"([^"]*)"`));
  return match ? match[1] : "";
}

function extractBooleanField(block, field) {
  const match = block.match(new RegExp(`"${field}"\\s*:\\s*(True|False)`));
  if (!match) return null;
  return match[1] === "True";
}

function extractRequestKeys(block) {
  const match = block.match(/"request_keys"\s*:\s*\[([^\]]*)\]/);
  if (!match) return [];
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]).sort();
}

function extractContracts() {
  const contracts = [];
  for (const file of contractFiles) {
    const source = readText(file);
    for (const block of extractObjectBlocks(source)) {
      const method = extractStringField(block, "method");
      const path = extractStringField(block, "path");
      if (!method || !path) continue;
      contracts.push({
        file,
        method,
        path,
        effect: extractStringField(block, "effect"),
        owner: extractStringField(block, "owner"),
        requires_confirmation: extractBooleanField(block, "requires_confirmation"),
        frontend_exposed: extractBooleanField(block, "frontend_exposed"),
        request_keys: extractRequestKeys(block),
        network_lifecycle: block.includes("\"network_lifecycle\""),
      });
    }
  }
  return contracts.sort((left, right) => `${left.method} ${left.path}`.localeCompare(`${right.method} ${right.path}`));
}

function expandIncludes(markup) {
  let expanded = markup;
  let changed = true;
  while (changed) {
    changed = false;
    expanded = expanded.replace(/<!--\s*mp-include:\s*([^>]+?)\s*-->/g, (_match, includePath) => {
      changed = true;
      return readText(repoRelative(`${webviewStaticRoot}/${includePath.trim()}`));
    });
  }
  return expanded;
}

function parseAttributes(raw) {
  const attrs = {};
  const attrRe = /([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*("[^"]*"|'[^']*'|[^\s"'=<>`]+)/g;
  for (const match of raw.matchAll(attrRe)) {
    attrs[match[1]] = match[2].replace(/^["']|["']$/g, "");
  }
  return attrs;
}

function cleanText(value) {
  return String(value || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function pageForOffset(markup, offset) {
  const before = markup.slice(0, offset);
  const matches = [...before.matchAll(/data-page-panel=["']([^"']+)["']/g)];
  return matches.length ? matches[matches.length - 1][1] : "app-shell";
}

function controlIdentity(control) {
  const dataAttrs = Object.entries(control.attrs)
    .filter(([name]) => name.startsWith("data-"))
    .map(([name, value]) => `${name}=${value}`)
    .join(" ");
  return [
    control.id,
    control.attrs.class || "",
    control.attrs.role || "",
    control.attrs.type || "",
    dataAttrs,
    control.text,
  ].join(" ");
}

function classifyControl(control) {
  const identity = controlIdentity(control);
  for (const rule of routeHintRules) {
    if (rule.pattern.test(identity)) {
      return {
        classification: rule.route.startsWith("contract:") ? "backend-contract-dynamic-route" : "backend-owned-route",
        route: rule.route,
      };
    }
  }
  for (const rule of localControlRules) {
    if (rule.pattern.test(identity)) {
      return { classification: rule.classification, route: "" };
    }
  }
  if (control.tag === "form") {
    return { classification: "local-form-staging", route: "" };
  }
  return { classification: "local-or-read-only", route: "" };
}

function collectControls(markup) {
  const controls = [];
  const pairedRe = /<(button|form|a)\b([^>]*)>([\s\S]*?)<\/\1>/gi;
  for (const match of markup.matchAll(pairedRe)) {
    const tag = match[1].toLowerCase();
    const attrs = parseAttributes(match[2] || "");
    if (tag === "a" && !attrs.href && !attrs.role && !Object.keys(attrs).some((key) => key.startsWith("data-"))) continue;
    const offset = match.index || 0;
    const control = {
      tag,
      id: attrs.id || "",
      page: pageForOffset(markup, offset),
      attrs,
      text: cleanText(match[3] || ""),
      source: `${tag}${attrs.id ? `#${attrs.id}` : ""}`,
    };
    controls.push({ ...control, ...classifyControl(control) });
  }
  const inputRe = /<(input|select|textarea)\b([^>]*)>/gi;
  for (const match of markup.matchAll(inputRe)) {
    const tag = match[1].toLowerCase();
    const attrs = parseAttributes(match[2] || "");
    const type = (attrs.type || tag).toLowerCase();
    const actionLike = ["button", "submit", "reset"].includes(type) || Object.keys(attrs).some((key) => key.startsWith("data-"));
    if (!actionLike) continue;
    const offset = match.index || 0;
    const control = {
      tag,
      id: attrs.id || "",
      page: pageForOffset(markup, offset),
      attrs,
      text: cleanText(attrs.value || attrs["aria-label"] || attrs.title || ""),
      source: `${tag}${attrs.id ? `#${attrs.id}` : ""}`,
    };
    controls.push({ ...control, ...classifyControl(control) });
  }
  return controls.sort((left, right) => left.page.localeCompare(right.page) || controlIdentity(left).localeCompare(controlIdentity(right)));
}

function ownerForScript(path) {
  if (/\/queue(?:View|\/)/.test(path)) return "Queue";
  if (/\/completed(?:View|\/)/.test(path)) return "Completed";
  if (/pendingPublish/.test(path)) return "Pending Publish";
  if (/rename/.test(path)) return "Rename";
  if (/settingsWizard/.test(path)) return "Settings Wizard";
  if (/settings|librariesRouteMap/.test(path)) return "Settings";
  if (/network/.test(path)) return "Network";
  if (/diagnostics|commandHistory/.test(path)) return "Diagnostics";
  if (/maintenance/.test(path)) return "Maintenance";
  if (/metrics/.test(path)) return "Metrics";
  if (/reports/.test(path)) return "Reports";
  if (/schedule/.test(path)) return "Schedule";
  if (/launch/.test(path)) return "Launch";
  if (/crossPageContextView\.sampleValidation/.test(path)) return "Cross Page";
  if (/home|app\.js|app\//.test(path)) return "App Shell";
  if (/apiClient|dom\/|domHelpers|formatters|progressView|tauriLifecycleBridge/.test(path)) return "Shared";
  return "Shared";
}

function allowedOwnersForRoute(route) {
  const normalized = normalizeRoute(route);
  const rule = routeOwnerRules.find((candidate) => candidate.route.test(route) || candidate.route.test(normalized));
  return rule ? rule.owners : ["Shared"];
}

function collectApiCalls(script) {
  const ast = parseScript(script.source, script.path);
  const calls = [];
  traverse(ast, {
    CallExpression(path) {
      const name = callName(path.node);
      if (!["apiGet", "apiPost", "apiPostLocal", "fetch"].includes(name)) return;
      const route = stringLiteralValue(path.node.arguments?.[0]);
      calls.push({
        function: name,
        route: route.startsWith("/api/") ? route : "",
        literal_route: Boolean(route && route.startsWith("/api/")),
        line: path.node.loc?.start?.line || 1,
      });
    },
  });
  return calls;
}

function dynamicApiPostAllowed(script, call) {
  if (script.path !== "apps/desktop/webview/static/assets/networkView.js") return false;
  if (call.function !== "apiPost") return false;
  return script.source.includes("route?.network_lifecycle")
    && script.source.includes("network_lifecycle_contracts")
    && script.source.includes("apiPost(route, request)")
    && script.source.includes("confirm_start")
    && script.source.includes("confirm_stop");
}

function routeSnippet(source, route) {
  const escaped = route.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const callMatch = source.match(new RegExp(`(?:apiPost|apiPostLocal)\\s*\\(\\s*["']${escaped}["']`));
  const index = callMatch?.index ?? source.indexOf(route);
  if (index < 0) return "";
  return source.slice(Math.max(0, index - 900), Math.min(source.length, index + 900));
}

function buildReport() {
  const indexHtml = readText(repoRelative(webviewIndexPath));
  const markup = expandIncludes(indexHtml);
  const contracts = extractContracts();
  const contractByPath = new Map(contracts.map((contract) => [`${contract.method} ${contract.path}`, contract]));
  const routeContractsByPath = new Map(contracts.map((contract) => [contract.path, contract]));
  const scripts = collectScriptTags(indexHtml)
    .map((src, index) => ({ index, src, path: scriptSrcToRepoPath(src) }))
    .filter((item) => item.path)
    .map((item) => {
      const analysis = analyzeScriptAsset(item.path);
      const source = readText(item.path);
      return {
        ...item,
        source,
        owner: ownerForScript(item.path),
        api_routes: analysis.api_routes,
        api_calls: collectApiCalls({ ...item, source }),
      };
    });

  const controls = collectControls(markup);
  const violations = [];

  const routeUsages = [];
  const dynamicApiPosts = [];
  for (const script of scripts) {
    for (const call of script.api_calls) {
      if (call.function === "fetch" && script.path !== "apps/desktop/webview/static/assets/apiClient.js") {
        violations.push({
          rule: "direct-fetch",
          file: script.path,
          line: call.line,
          message: "Only apiClient.js may call fetch directly.",
        });
      }
      if (["apiPost", "apiPostLocal"].includes(call.function) && !call.literal_route) {
        const allowed = dynamicApiPostAllowed(script, call);
        dynamicApiPosts.push({ file: script.path, line: call.line, allowed, reason: allowed ? "contract-driven Network lifecycle dispatch" : "non-literal apiPost route" });
        if (!allowed) {
          violations.push({
            rule: "nonliteral-api-post",
            file: script.path,
            line: call.line,
            message: "apiPost routes must be literal unless they are the contract-driven Network lifecycle dispatcher.",
          });
        }
      }
      if (!call.route) continue;
      const normalized = normalizeRoute(call.route);
      const method = call.function === "apiGet" ? "GET" : "POST";
      const contract = contractByPath.get(`${method} ${normalized}`) || routeContractsByPath.get(normalized);
      const allowedOwners = allowedOwnersForRoute(call.route);
      const readOnlySharedOwner = method === "GET" && ["App Shell", "Shared"].includes(script.owner);
      const ownerOk = readOnlySharedOwner || allowedOwners.includes(script.owner) || allowedOwners.includes("Shared") || script.owner === "Shared";
      routeUsages.push({
        route: call.route,
        normalized_route: normalized,
        method,
        file: script.path,
        line: call.line,
        script_owner: script.owner,
        allowed_owners: allowedOwners,
        contract_effect: contract?.effect || "",
        high_risk_effect: contract ? highRiskEffects.has(contract.effect) : false,
        contract_found: Boolean(contract),
        owner_ok: ownerOk,
      });
      if (!contract) {
        violations.push({
          rule: "undocumented-api-route",
          route: call.route,
          file: script.path,
          line: call.line,
          message: `${method} ${normalized} is not documented in LOCAL_API_ROUTE_CONTRACT.`,
        });
      }
      if (!ownerOk) {
        violations.push({
          rule: "route-owner-mismatch",
          route: call.route,
          file: script.path,
          line: call.line,
          message: `${script.owner} asset calls ${call.route}, expected owner ${allowedOwners.join(" or ")}.`,
        });
      }
    }
  }

  for (const rule of confirmationRules) {
    const literalRouteFiles = scripts
      .filter((script) => script.api_calls.some((call) => ["apiPost", "apiPostLocal"].includes(call.function) && call.route === rule.route));
    const evidenceFiles = literalRouteFiles.length
      ? literalRouteFiles
      : scripts.filter((script) => (rule.evidenceFiles || []).includes(script.path));
    const files = evidenceFiles
      .map((script) => ({
        file: script.path,
        has_confirmation: rule.pattern.test(literalRouteFiles.length ? routeSnippet(script.source, rule.route) : script.source),
      }));
    if (!files.length || files.some((file) => !file.has_confirmation)) {
      violations.push({
        rule: "confirmation-required",
        route: rule.route,
        confirmation: rule.confirmation,
        files: files.map((file) => file.file),
        message: `${rule.route} must include ${rule.confirmation} evidence near the posted route.`,
      });
    }
  }

  for (const rule of selectorRouteRules) {
    for (const script of scripts.filter((item) => item.api_calls.some((call) => ["apiPost", "apiPostLocal"].includes(call.function) && call.route === rule.route))) {
      const snippet = routeSnippet(script.source, rule.route);
      for (const key of rule.required) {
        if (!new RegExp(`\\b${key}\\b`).test(snippet)) {
          violations.push({
            rule: "selector-key-required",
            route: rule.route,
            file: script.path,
            key,
            message: `${rule.route} must submit backend selector key ${key}.`,
          });
        }
      }
      for (const key of rule.forbidden) {
        if (new RegExp(`\\b${key}\\s*:`).test(snippet)) {
          violations.push({
            rule: "raw-path-key-forbidden",
            route: rule.route,
            file: script.path,
            key,
            message: `${rule.route} must not submit raw filesystem key ${key}.`,
          });
        }
      }
    }
  }

  for (const script of scripts) {
    for (const rule of directMutationApiRules) {
      if (rule.allowed.includes(script.path)) continue;
      if (rule.pattern.test(script.source)) {
        violations.push({
          rule: "forbidden-frontend-api",
          label: rule.label,
          file: script.path,
          message: `${rule.label} is not allowed in WebView assets.`,
        });
      }
    }
  }

  const unclassifiedHighRiskControls = controls.filter((control) => {
    const identity = controlIdentity(control).toLowerCase();
    const hasHighRiskTerm = highRiskControlTerms.some((term) => identity.includes(term));
    return hasHighRiskTerm && control.classification === "local-or-read-only";
  });
  for (const control of unclassifiedHighRiskControls) {
    violations.push({
      rule: "unclassified-high-risk-control",
      page: control.page,
      id: control.id,
      text: control.text,
      message: "High-risk action-like control must be classified as backend-owned or explicit local staging/navigation.",
    });
  }

  const controlsByClassification = controls.reduce((counts, control) => {
    counts[control.classification] = (counts[control.classification] || 0) + 1;
    return counts;
  }, {});

  return {
    schema_version: "webview_command_boundary_audit.v1",
    generated_by: "ops/scripts/dev/check-webview-command-boundary.mjs",
    source_index: repoRelative(webviewIndexPath),
    guard_note: "Every action-like WebView control is classified. Mutation-capable behavior must be represented as documented backend-owned Local API routes; local behavior is limited to staging, filtering, selection, navigation, clipboard, layout/theme, and blocked guard evidence.",
    ok: violations.length === 0,
    violations,
    summary: {
      scripts: scripts.length,
      controls: controls.length,
      route_usages: routeUsages.length,
      dynamic_api_posts: dynamicApiPosts.length,
      route_contracts: contracts.length,
      high_risk_route_usages: routeUsages.filter((usage) => usage.high_risk_effect).length,
      unclassified_high_risk_controls: unclassifiedHighRiskControls.length,
      controls_by_classification: Object.fromEntries(Object.entries(controlsByClassification).sort(([left], [right]) => left.localeCompare(right))),
    },
    controls: controls.map((control) => ({
      page: control.page,
      tag: control.tag,
      id: control.id,
      text: control.text,
      classification: control.classification,
      route: control.route,
      data_attrs: Object.fromEntries(Object.entries(control.attrs).filter(([key]) => key.startsWith("data-")).sort(([left], [right]) => left.localeCompare(right))),
    })),
    route_usages: routeUsages.sort((left, right) => `${left.route} ${left.file} ${left.line}`.localeCompare(`${right.route} ${right.file} ${right.line}`)),
    dynamic_api_posts: dynamicApiPosts,
    route_contracts: contracts.map((contract) => ({
      method: contract.method,
      path: contract.path,
      effect: contract.effect,
      owner: contract.owner,
      requires_confirmation: contract.requires_confirmation,
      frontend_exposed: contract.frontend_exposed,
      network_lifecycle: contract.network_lifecycle,
      request_keys: contract.request_keys,
    })),
  };
}

const args = parseArgs(process.argv.slice(2));
const report = buildReport();
const staleOrWriteExit = writeOrCheckJson(outputPath, report, args.check);
if (report.violations.length) {
  report.violations.forEach((violation) => console.error(`${violation.rule}: ${violation.message}`));
  process.exitCode = 1;
} else {
  process.exitCode = staleOrWriteExit;
}
