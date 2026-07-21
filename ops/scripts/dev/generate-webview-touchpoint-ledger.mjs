import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

import {
  analyzeScriptAsset,
  collectEventBindings,
  collectHtmlControls,
  collectJsFiles,
  readText,
  repoRelative,
  repoRoot,
  sortedUniq,
  webviewIndexPath,
  writeOrCheckJson,
} from "./webview-tooling-common.mjs";

const outputPath = "docs/generated/WEBVIEW_TOUCHPOINT_LEDGER.json";
const evidencePath = "docs/inventories/WEBVIEW_TOUCHPOINT_EVIDENCE.json";
const commandBoundaryPath = "docs/generated/WEBVIEW_COMMAND_BOUNDARY_AUDIT.json";
const domInventoryPath = "docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md";
const smokeWrapperMapPath = "docs/generated/SMOKE_WRAPPER_MAP.json";
const smokeCatalogPath = "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md";
const staticRoot = "apps/desktop/webview/static";
const auxiliaryStaticPages = [
  {
    path: "apps/desktop/webview/static/assets/pipelineLogWindow.html",
    surfaceFallback: "pipeline-log-window",
  },
];

const allowedDispositionCategories = new Set([
  "automated_passed",
  "missing_browser_prerequisite",
  "missing_fixture_or_backend_state",
  "lifecycle_state_precondition_not_constructed",
  "intentionally_hidden_or_feature_gated",
  "native_os_tauri_interaction_unavailable",
  "unsafe_mutation_excluded_by_no_mutation_policy",
  "unsupported_or_not_applicable",
  "duplicate_coverage_with_traceable_evidence",
  "harness_limitation",
  "flaky_synchronization",
  "product_defect",
  "stale_inventory_entry",
  "unexplained_evidence_gap",
]);

const dispositionProfiles = {
  automated_passed: {
    closure_class: "automated_passed",
    why_it_matters: "A rerunnable browser, contract, or native test produced the required evidence for the authored interaction.",
    automation_feasible: true,
    automation_scope: "Acceptance automation may count this interaction only while the cited test completes without skips.",
    next_evidence_action: "Keep the cited test in the acceptance inventory and rerun it when the owning surface changes.",
  },
  missing_browser_prerequisite: {
    closure_class: "legitimately_blocked",
    why_it_matters: "No browser assertion ran, so a skipped module must not be reported as passing evidence.",
    automation_feasible: true,
    automation_scope: "Install Node.js and Chrome or Edge, then rerun the canonical browser wrapper.",
    next_evidence_action: "Satisfy the emitted prerequisite record and rerun the exact browser selector without the skip opt-out.",
  },
  missing_fixture_or_backend_state: {
    closure_class: "legitimately_blocked",
    why_it_matters: "The control cannot be credited until its supported visible and enabled state is constructed and asserted.",
    automation_feasible: true,
    automation_scope: "Use generated temporary backend state and disposable roots; never manufacture state in a personal or live library.",
    next_evidence_action: "Add a focused disposable-state browser test that constructs the prerequisite, physically activates the control, and proves its final state or backend effect.",
  },
  lifecycle_state_precondition_not_constructed: {
    closure_class: "legitimately_blocked",
    why_it_matters: "Lifecycle controls are meaningful only when exact owned-process or run identity is present.",
    automation_feasible: true,
    automation_scope: "Use a temporary backend or controlled child process with exact-process cleanup and no media work.",
    next_evidence_action: "Construct the exact lifecycle state in an isolated harness, activate the control, verify the command identity, and prove cleanup.",
  },
  intentionally_hidden_or_feature_gated: {
    closure_class: "legitimately_blocked",
    why_it_matters: "A hidden, disabled, or future-gated control has no supported operator activation path in the observed configuration.",
    automation_feasible: false,
    automation_scope: "Automation becomes applicable only when a supported configuration or production handler makes the control reachable.",
    next_evidence_action: "Either provide a supported reachability fixture and test it, or remove/document the stale or future-only authored control.",
  },
  native_os_tauri_interaction_unavailable: {
    closure_class: "manual_native_only",
    why_it_matters: "Browser automation cannot prove the actual Windows picker, OS shell, external application, or native WebView2 outcome.",
    automation_feasible: false,
    automation_scope: "Keep backend route contracts automated, but retain the genuine native outcome as Windows/Tauri evidence.",
    next_evidence_action: "Run the cited native/manual recipe and capture the selected path, opened target, window state, failure evidence, and isolated-root proof.",
  },
  unsafe_mutation_excluded_by_no_mutation_policy: {
    closure_class: "intentionally_excluded",
    why_it_matters: "The interaction can move, delete, publish, persist, or otherwise mutate state beyond the no-mutation census boundary.",
    automation_feasible: true,
    automation_scope: "It may move to automated evidence only with a purpose-built disposable fixture, explicit rollback proof, and the existing backend confirmation boundary.",
    next_evidence_action: "Retain exclusion until a focused temporary-root test proves the full effect and rollback without touching source, output, scratch, or personal state.",
  },
  unsupported_or_not_applicable: {
    closure_class: "intentionally_excluded",
    why_it_matters: "The interaction is outside the supported product state or does not apply to this build.",
    automation_feasible: false,
    automation_scope: "No acceptance automation is required while the owning contract remains unsupported or inapplicable.",
    next_evidence_action: "Reclassify only when the product contract changes; otherwise remove any stale authored surface.",
  },
  duplicate_coverage_with_traceable_evidence: {
    closure_class: "automated_passed",
    why_it_matters: "A focused rerunnable test supplies stronger evidence than the broad census exception that originally covered this control.",
    automation_feasible: true,
    automation_scope: "The focused test must physically activate the exact stable control identity and assert its applicable effect.",
    next_evidence_action: "Keep the focused test and its stable control identity linked in this ledger.",
  },
  harness_limitation: {
    closure_class: "legitimately_blocked",
    why_it_matters: "The current harness cannot observe or construct a required product boundary, so absence of evidence is not a pass.",
    automation_feasible: true,
    automation_scope: "Improve the isolated harness without weakening product guards or replacing native proof with a browser stub.",
    next_evidence_action: "Add the missing observation or fixture capability and rerun the exact control evidence test.",
  },
  flaky_synchronization: {
    closure_class: "automated_but_failing",
    why_it_matters: "A nondeterministic result cannot serve as release evidence.",
    automation_feasible: true,
    automation_scope: "Use observable readiness/final-state conditions and bounded retries; do not hide the failure with sleeps or skip allowances.",
    next_evidence_action: "Capture the failing artifact, remove the race, and repeat the focused test until the acceptance threshold is met.",
  },
  product_defect: {
    closure_class: "automated_but_failing",
    why_it_matters: "The interaction was reachable but did not meet its authored product contract.",
    automation_feasible: true,
    automation_scope: "Keep the failing test active while the product defect is repaired.",
    next_evidence_action: "Link a stable finding, fix the product behavior, and rerun the focused and neighboring workflow tests.",
  },
  stale_inventory_entry: {
    closure_class: "stale_entries_removed",
    why_it_matters: "A removed or unreachable authored identity must not remain in the current denominator.",
    automation_feasible: false,
    automation_scope: "Source-derived regeneration is the authority for current authored identities.",
    next_evidence_action: "Remove the stale overlay entry and regenerate inventories and the touchpoint ledger.",
  },
  unexplained_evidence_gap: {
    closure_class: "unexplained_gaps",
    why_it_matters: "An authored interaction lacks a traceable pass, blocker, native recipe, intentional exclusion, or product finding.",
    automation_feasible: true,
    automation_scope: "The gap must be classified before the ledger can be accepted.",
    next_evidence_action: "Assign an explicit supported disposition and evidence-producing owner action.",
  },
};

function parseArgs(argv) {
  return {
    check: argv.includes("--check"),
    write: argv.includes("--write") || !argv.includes("--check"),
  };
}

function includeFragments(indexHtml) {
  const fragments = [{
    path: repoRelative(webviewIndexPath),
    html: indexHtml.replace(/<!--\s*mp-include:\s*([^>]+?)\s*-->/g, ""),
    surfaceFallback: "app-shell",
  }];
  for (const match of indexHtml.matchAll(/<!--\s*mp-include:\s*([^>]+?)\s*-->/g)) {
    const includePath = String(match[1] || "").trim().replaceAll("\\", "/");
    const path = `${staticRoot}/${includePath}`;
    const fileName = includePath.split("/").at(-1) || "";
    const pageMatch = fileName.match(/^page-([^.]+)\.html$/);
    const surfaceFallback = pageMatch
      ? pageMatch[1]
      : /settings-save-review-dialog/.test(fileName)
        ? "settings-save-dialog"
        : "app-shell";
    fragments.push({ path, html: readText(path), surfaceFallback });
  }
  return fragments;
}

function slug(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}

function semanticDataAttributes(attrs) {
  return Object.entries(attrs || {})
    .filter(([name, value]) => name.startsWith("data-") && value)
    .filter(([name]) => /(action|command|mode|open|page|scope|tab|target|toggle|control|dialog|step|route|kind|filter)/.test(name))
    .sort(([left], [right]) => left.localeCompare(right));
}

function semanticControlKey(control) {
  if (control.attrs["data-touchpoint-id"]) return slug(control.attrs["data-touchpoint-id"]);
  const dataKey = semanticDataAttributes(control.attrs)
    .map(([name, value]) => `${slug(name.replace(/^data-/, ""))}-${slug(value)}`)
    .join("-");
  const parts = [
    slug(control.tag),
    slug(control.type || control.role),
    dataKey,
    slug(control.attrs.name || ""),
    slug(control.attrs.value || ""),
    slug(control.label),
  ].filter(Boolean);
  return parts.join("-") || "unnamed-control";
}

function touchpointId(control) {
  if (control.id) return `webview.static.${control.id}`;
  if (control.attrs["data-touchpoint-id"]) return `webview.static.${slug(control.attrs["data-touchpoint-id"])}`;
  return `webview.static.${slug(control.surface)}.${semanticControlKey(control)}`;
}

function selectorFor(control) {
  if (control.id) return `#${control.id}`;
  if (control.attrs["data-touchpoint-id"]) return `[data-touchpoint-id="${control.attrs["data-touchpoint-id"]}"]`;
  const dataAttrs = semanticDataAttributes(control.attrs);
  if (dataAttrs.length) {
    return `${control.tag}${dataAttrs.map(([name, value]) => `[${name}="${value}"]`).join("")}`;
  }
  if (control.attrs.name) return `${control.tag}[name="${control.attrs.name}"]`;
  if (control.role) return `${control.tag}[role="${control.role}"]`;
  return control.tag;
}

function commandControlScore(control, candidate) {
  if (control.id || candidate.id) return control.id && candidate.id === control.id ? 1000 : -1;
  if (candidate.tag !== control.tag) return -1;
  let score = 0;
  const candidateAttrs = candidate.data_attrs || {};
  for (const [name, value] of Object.entries(candidateAttrs)) {
    if (control.attrs[name] === value) score += 20;
    else return -1;
  }
  const candidateText = slug(candidate.text);
  const controlText = slug(control.label);
  if (candidateText && candidateText === controlText) score += 10;
  if (candidate.page === control.surface) score += 5;
  return score;
}

function matchingCommandControl(control, commandControls) {
  const scored = commandControls
    .map((candidate) => ({ candidate, score: commandControlScore(control, candidate) }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score);
  if (!scored.length) return null;
  if (scored.length > 1 && scored[0].score === scored[1].score) return null;
  return scored[0].candidate;
}

function defaultLocalClassification(control) {
  if (["input", "select", "textarea"].includes(control.tag)) return "local-form-staging";
  if (control.role === "tab" || control.attrs["data-page"] || control.attrs["data-settings-tab"]) return "local-tab-navigation";
  if (control.tag === "summary") return "local-display-state";
  if (control.attrs["data-network-future-control"] !== undefined) return "disabled-future-network-control";
  return "local-or-read-only";
}

function actionFor(control, commandControl, routeEffects) {
  const classification = commandControl?.classification || defaultLocalClassification(control);
  const route = commandControl?.route || "";
  const normalizedRoute = route.startsWith("contract:") ? route.slice("contract:".length) : route;
  const effect = routeEffects.get(normalizedRoute) || "";
  const kind = route
    ? "api_command"
    : classification.includes("navigation")
      ? "local_navigation"
      : classification.includes("staging")
        ? "local_staging"
        : classification === "local-display-state"
          ? "local_display"
          : "local_or_read_only";
  return { kind, method: route ? "POST" : null, route: normalizedRoute || null, command: null, effect: effect || null, ownership_classification: classification };
}

function defaultSafety(control, action) {
  const identity = `${control.id} ${control.label} ${selectorFor(control)}`.toLowerCase();
  if (/tdarr-matrix-delete-confirm|cleanup-delete|delete verified full matrix/.test(identity)) {
    return { status: "destructive", reason: "Arms or invokes permanent verified-matrix deletion; dynamic execution is intentionally skipped." };
  }
  if (action.ownership_classification === "disabled-future-network-control") {
    return { status: "unreachable", reason: "Authored as a disabled future Network control." };
  }
  if (action.effect && !["none", "shell-open", "shell-dialog"].includes(action.effect)) {
    return { status: "safe_reversible", reason: `Backend-owned ${action.effect} command is reversible only inside a verified disposable root.` };
  }
  return { status: "safe", reason: "Read-only, navigation, display, or local staging interaction." };
}

function expectedTransition(action) {
  if (action.route) return `Submit ${action.method} ${action.route} through the owning WebView handler and render backend result/status evidence.`;
  if (action.kind === "local_navigation") return "Change the active page, tab, focus target, or selected evidence surface without backend mutation.";
  if (action.kind === "local_staging") return "Update staged operator intent and dependent preview/validation state without committing backend mutation.";
  if (action.kind === "local_display") return "Update local visibility, disclosure, filter, sort, or layout state.";
  return "Perform the authored local/read-only interaction and keep backend-owned mutation boundaries intact.";
}

function requiredEvidence(action) {
  const evidence = ["physical DOM event", "visible/enabled-state assertion", "stable final UI assertion"];
  if (action.route) evidence.push("backend route observation", "command journal or response evidence");
  if (action.kind === "local_staging") evidence.push("staged-value assertion", "reset/revisit assertion where persistence applies");
  return evidence;
}

function recursiveFiles(root, predicate) {
  const result = [];
  if (!existsSync(root)) return result;
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isDirectory()) result.push(...recursiveFiles(path, predicate));
    else if (entry.isFile() && predicate(path)) result.push(path);
  }
  return result.sort();
}

function domInventoryReconciliation(staticControls) {
  const inventory = readText(domInventoryPath);
  const manifestMatch = inventory.match(/<!-- BEGIN GENERATED DOM ID MANIFEST -->([\s\S]*?)<!-- END GENERATED DOM ID MANIFEST -->/);
  if (!manifestMatch) throw new Error(`${domInventoryPath} is missing its generated DOM ID manifest.`);
  const documentSections = [...manifestMatch[1].matchAll(/Count:\s*(\d+)\s*```text\s*([\s\S]*?)\s*```/g)]
    .map((match) => ({
      declared_count: Number(match[1]),
      ids: match[2].split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
    }));
  if (!documentSections.length) throw new Error(`${domInventoryPath} has no document-scoped ID sections.`);
  for (const section of documentSections) {
    if (section.declared_count !== section.ids.length) {
      throw new Error(`${domInventoryPath} section declares ${section.declared_count} IDs but lists ${section.ids.length}.`);
    }
  }
  const inventoryIds = sortedUniq(documentSections.flatMap((section) => section.ids));
  const inventoryIdSet = new Set(inventoryIds);
  const authoredControlIds = sortedUniq(staticControls.map((control) => control.id).filter(Boolean));
  const missingControlIds = authoredControlIds.filter((id) => !inventoryIdSet.has(id));
  if (missingControlIds.length) {
    throw new Error(`${domInventoryPath} omits ${missingControlIds.length} authored control ID(s): ${missingControlIds.slice(0, 20).join(", ")}`);
  }
  const totalMatch = inventory.match(/Total document-scoped element IDs:\s*\*\*(\d+)\*\*/);
  const documentScopedCount = documentSections.reduce((total, section) => total + section.ids.length, 0);
  if (!totalMatch || Number(totalMatch[1]) !== documentScopedCount) {
    throw new Error(`${domInventoryPath} count prose does not match its ${inventoryIds.length}-ID generated manifest.`);
  }
  return {
    inventory_path: domInventoryPath,
    inventory_document_count: documentSections.length,
    inventory_document_scoped_id_count: documentScopedCount,
    inventory_globally_unique_id_count: inventoryIds.length,
    authored_control_id_count: authoredControlIds.length,
    authored_control_ids_missing_from_inventory: 0,
  };
}

function browserEvidenceInventory(browserTests) {
  const smokeMap = JSON.parse(readText(smokeWrapperMapPath));
  if ((smokeMap.drift_findings || []).length) {
    throw new Error(`${smokeWrapperMapPath} contains ${smokeMap.drift_findings.length} drift finding(s).`);
  }
  const actualWrapperPaths = recursiveFiles(join(repoRoot, "ops", "scripts", "smoke"), (path) => /Test-WebViewBrowser.*\.ps1$/i.test(path))
    .map((path) => repoRelative(path));
  const mappedBrowserWrappers = (smokeMap.wrappers || []).filter((wrapper) => wrapper.proof_tier === "browser_smoke");
  const mappedWrapperPaths = sortedUniq(mappedBrowserWrappers.map((wrapper) => wrapper.path));
  if (JSON.stringify(actualWrapperPaths) !== JSON.stringify(mappedWrapperPaths)) {
    throw new Error(`${smokeWrapperMapPath} browser-wrapper paths do not match ops/scripts/smoke.`);
  }
  const catalog = readText(smokeCatalogPath);
  const catalogBrowserWrappers = sortedUniq(
    [...catalog.matchAll(/^###\s+`(Test-WebViewBrowser[^`]+\.ps1)`/gm)].map((match) => `ops/scripts/smoke/${match[1]}`),
  );
  if (JSON.stringify(catalogBrowserWrappers) !== JSON.stringify(actualWrapperPaths)) {
    throw new Error(`${smokeCatalogPath} browser-wrapper headings do not match ops/scripts/smoke.`);
  }
  const browserModules = sortedUniq(browserTests.map((test) => test.path));
  const wrappedModules = new Set();
  for (const wrapper of mappedBrowserWrappers) {
    for (const selector of wrapper.test_selectors || []) {
      const moduleMatch = String(selector).match(/^(tests\.webview\.test_webview_browser[^.]+)/);
      if (moduleMatch) wrappedModules.add(`${moduleMatch[1].replaceAll(".", "/")}.py`);
    }
  }
  const directOnlyModules = browserModules.filter((path) => !wrappedModules.has(path));
  return {
    wrapper_map_path: smokeWrapperMapPath,
    catalog_path: smokeCatalogPath,
    browser_wrapper_count: actualWrapperPaths.length,
    browser_test_module_count: browserModules.length,
    wrapped_browser_test_module_count: browserModules.length - directOnlyModules.length,
    direct_only_browser_test_modules: directOnlyModules,
  };
}

function browserReferences(control, browserTests) {
  const needles = [control.id, control.attrs["data-touchpoint-id"], ...semanticDataAttributes(control.attrs).map(([, value]) => value)]
    .filter((value) => String(value || "").length >= 4);
  if (!needles.length) return [];
  return browserTests
    .filter((test) => needles.some((needle) => test.source.includes(String(needle))))
    .map((test) => test.path);
}

function loadOverlay() {
  if (!existsSync(join(repoRoot, evidencePath))) {
    throw new Error(`${evidencePath} is missing; touchpoint classification evidence is required.`);
  }
  return JSON.parse(readText(evidencePath));
}

function validateAuditResult(audit, context) {
  const allowed = new Set(["not_run", "passed", "blocked", "skipped", "failed", "flaky"]);
  if (!allowed.has(audit?.status)) throw new Error(`${context} has invalid audit status: ${audit?.status}`);
  if (audit.status === "passed" && !(audit.tests || []).length) {
    throw new Error(`${context} claims passed without a rerunnable test.`);
  }
  if (["blocked", "skipped", "failed", "flaky"].includes(audit.status) && !audit.blocker) {
    throw new Error(`${context} requires a concrete blocker/failure reason.`);
  }
  for (const path of audit.tests || []) {
    if (!existsSync(join(repoRoot, path))) throw new Error(`${context} references missing test: ${path}`);
  }
  return audit;
}

function dispositionFields(source) {
  return {
    reason_category: source?.reason_category || null,
    disposition_id: source?.disposition_id || null,
    exact_prerequisite: source?.exact_prerequisite || null,
    why_it_matters: source?.why_it_matters || null,
    automation_feasible: typeof source?.automation_feasible === "boolean" ? source.automation_feasible : null,
    automation_scope: source?.automation_scope || null,
    next_evidence_action: source?.next_evidence_action || null,
    owner: source?.owner || null,
  };
}

function nativeRecipeFor(action, touchpointId) {
  if (touchpointId === "tauri.native.pipeline-log-window.content-uia") return "TAURI-PIPELINE-LOG-UIA-001";
  if (touchpointId === "tauri.native.pipeline-log-window.independent-close") return "TAURI-PIPELINE-LOG-CLOSE-001";
  if (action?.effect === "shell-dialog" || action?.kind === "native_or_backend_picker" || /path-picker/.test(action?.route || "")) return "NATIVE-PICKER-ISOLATION-001";
  if (action?.effect === "shell-open") return "NATIVE-OS-SHELL-OPEN-001";
  return "TAURI-NATIVE-BOUNDARY-001";
}

function dispositionForRecord(record) {
  const audit = record.audit || {};
  let category = audit.reason_category || null;
  if (!category && audit.status === "passed") category = "automated_passed";
  if (!category && audit.status === "not_run") category = "unexplained_evidence_gap";
  if (!category) {
    throw new Error(`${record.touchpoint_id} has ${audit.status} evidence without an explicit disposition reason_category.`);
  }
  if (!allowedDispositionCategories.has(category) || !dispositionProfiles[category]) {
    throw new Error(`${record.touchpoint_id} has unsupported disposition category: ${category}`);
  }
  const profile = dispositionProfiles[category];
  const passed = audit.status === "passed";
  const exactPrerequisite = audit.exact_prerequisite
    || (passed
      ? "The cited rerunnable test completed the control's authored visibility, enabled-state, activation, and final-evidence prerequisites without a skip."
      : audit.blocker);
  if (!exactPrerequisite) throw new Error(`${record.touchpoint_id} has no exact evidence prerequisite.`);
  const tests = sortedUniq(audit.tests || []);
  const evidence = sortedUniq(audit.evidence || []);
  const owner = audit.owner
    || (record.origin === "tauri_native_family" ? "tauri-native-qa" : "webview-browser-qa");
  if (!owner && !tests.length) throw new Error(`${record.touchpoint_id} has neither an evidence owner nor a test reference.`);
  return {
    category,
    closure_class: profile.closure_class,
    exact_prerequisite: exactPrerequisite,
    why_it_matters: audit.why_it_matters || profile.why_it_matters,
    automation_feasible: typeof audit.automation_feasible === "boolean" ? audit.automation_feasible : profile.automation_feasible,
    automation_scope: audit.automation_scope || profile.automation_scope,
    next_evidence_action: audit.next_evidence_action || profile.next_evidence_action,
    owner,
    test_references: tests,
    evidence_references: evidence,
    current_evidence_state: audit.status,
    manual_recipe: category === "native_os_tauri_interaction_unavailable"
      ? (audit.manual_recipe || nativeRecipeFor(record.action, record.touchpoint_id))
      : null,
  };
}

function stableControlIdentity(record) {
  return {
    page: record.surface?.page || null,
    panel: record.surface?.panel || record.surface?.page || null,
    workflow: record.audit?.run_id || record.touchpoint_id,
    dom_id: record.locator?.dom_id || null,
    selector: record.locator?.selector || null,
    control_type: record.locator?.tag || record.locator?.role || record.origin,
    backend_route: record.action?.route || null,
    local_only_behavior: record.action?.route ? null : (record.action?.effect || record.action?.kind || null),
    mutation_classification: record.classification?.status || null,
    expected_prerequisite: record.disposition?.exact_prerequisite || null,
    test_owner: record.disposition?.owner || null,
    current_evidence_state: record.audit?.status || null,
    disposition: record.disposition?.closure_class || null,
  };
}

function defaultAuditFor(safety, references) {
  if (safety.status === "destructive") {
    return {
      status: "skipped",
      tests: [],
      evidence: references,
      blocker: safety.reason,
      reason_category: "unsafe_mutation_excluded_by_no_mutation_policy",
    };
  }
  if (safety.status === "unreachable") {
    return {
      status: "blocked",
      tests: [],
      evidence: references,
      blocker: safety.reason,
      reason_category: "intentionally_hidden_or_feature_gated",
    };
  }
  return {
    status: "not_run",
    tests: [],
    evidence: references,
    blocker: "No per-touchpoint physical activation result has been curated yet.",
    reason_category: "unexplained_evidence_gap",
  };
}

function auditForStaticRecord({ id, control, safety, references, override, staticAuditRuns, focusedEvidenceGroups }) {
  if (override.audit) return validateAuditResult(override.audit, `static override ${id}`);
  if (["destructive", "unreachable"].includes(safety.status)) return defaultAuditFor(safety, references);

  const focusedMatches = focusedEvidenceGroups.filter((group) => (group.touchpoint_ids || []).includes(id));
  if (focusedMatches.length > 1) {
    throw new Error(`Static touchpoint ${id} has overlapping focused evidence: ${focusedMatches.map((group) => group.evidence_id).join(", ")}`);
  }
  if (focusedMatches.length === 1) {
    const focused = focusedMatches[0];
    return validateAuditResult({
      status: "passed",
      tests: focused.tests || [],
      evidence: focused.evidence || [],
      blocker: null,
      run_id: focused.evidence_id,
      reason_category: "duplicate_coverage_with_traceable_evidence",
      exact_prerequisite: focused.exact_prerequisite || null,
      why_it_matters: focused.why_it_matters || null,
      automation_feasible: true,
      automation_scope: focused.automation_scope || null,
      next_evidence_action: focused.next_evidence_action || null,
      owner: focused.owner || "webview-browser-qa",
    }, `focused evidence ${focused.evidence_id} for ${id}`);
  }

  const matchingRuns = staticAuditRuns.filter((run) => (run.surfaces || []).includes(control.surface));
  if (matchingRuns.length > 1) {
    throw new Error(`Static touchpoint ${id} is covered by overlapping audit runs: ${matchingRuns.map((run) => run.run_id).join(", ")}`);
  }
  if (!matchingRuns.length) return defaultAuditFor(safety, references);

  const run = matchingRuns[0];
  const groupedExceptions = (run.exception_groups || []).filter((group) => (group.touchpoint_ids || []).includes(id));
  const directException = run.exceptions?.[id];
  if (groupedExceptions.length + (directException ? 1 : 0) > 1) {
    throw new Error(`Static touchpoint ${id} has overlapping exceptions in audit run ${run.run_id}.`);
  }
  const exception = directException || groupedExceptions[0];
  if (exception) {
    return validateAuditResult({
      status: exception.status,
      tests: exception.tests || run.tests || [],
      evidence: exception.evidence || run.evidence || [],
      blocker: exception.blocker || null,
      run_id: run.run_id,
      ...dispositionFields(exception),
    }, `static audit exception ${id}`);
  }
  return validateAuditResult({
    status: run.status || "passed",
    tests: run.tests || [],
    evidence: run.evidence || [],
    blocker: run.blocker || null,
    run_id: run.run_id,
    ...dispositionFields(run),
  }, `static audit run ${run.run_id} for ${id}`);
}

function sourceEvidenceFor(control, scriptAnalyses, bindingsByFile, scriptSources) {
  const sources = [{ path: control.source_path, line: control.source_line, event: null, handler: null, binding_scope: "markup" }];
  const matchingScripts = [];
  if (control.id) {
    matchingScripts.push(...scriptAnalyses.filter((item) => item.analysis.dom_ids_touched.includes(control.id)).map((item) => item.path));
  }
  if (!matchingScripts.length) {
    const needles = [control.id, ...semanticDataAttributes(control.attrs).map(([, value]) => value)].filter((value) => String(value || "").length >= 4);
    matchingScripts.push(...scriptSources.filter((item) => needles.some((needle) => item.source.includes(String(needle)))).map((item) => item.path));
  }
  for (const path of sortedUniq(matchingScripts).slice(0, 12)) {
    const exactBindings = (bindingsByFile.get(path) || []).filter((binding) => {
      if (binding.target.kind === "dom_id" && control.id) return binding.target.value === control.id;
      if (binding.target.kind !== "selector") return false;
      if (binding.target.value === selectorFor(control)) return true;
      return Boolean(control.id && binding.target.value.includes(`#${control.id}`));
    });
    if (exactBindings.length) {
      for (const binding of exactBindings) {
        sources.push({ path, line: binding.line, event: binding.event, handler: binding.handler, binding_scope: "exact" });
      }
    } else {
      const delegatedBindings = (bindingsByFile.get(path) || [])
        .filter((binding) => binding.target.kind === "global")
        .slice(0, 12);
      if (delegatedBindings.length) {
        for (const binding of delegatedBindings) {
          sources.push({ path, line: binding.line, event: binding.event, handler: binding.handler, binding_scope: "delegated-source" });
        }
      } else {
        sources.push({ path, line: 0, event: null, handler: null, binding_scope: "source-reference" });
      }
    }
  }
  return sources;
}

function buildLedger() {
  const indexHtml = readText(repoRelative(webviewIndexPath));
  const fragments = includeFragments(indexHtml);
  const mainStaticControls = fragments.flatMap((fragment) => collectHtmlControls(fragment.html, {
    sourcePath: fragment.path,
    surfaceFallback: fragment.surfaceFallback,
  }));
  const auxiliaryStaticControls = auxiliaryStaticPages.flatMap((page) => {
    return collectHtmlControls(readText(page.path), {
      sourcePath: page.path,
      surfaceFallback: page.surfaceFallback,
    });
  });
  const staticControls = [...mainStaticControls, ...auxiliaryStaticControls];
  const domReconciliation = domInventoryReconciliation(staticControls);

  const idGroups = new Map();
  for (const control of staticControls) {
    const id = touchpointId(control);
    const group = idGroups.get(id) || [];
    group.push(control);
    idGroups.set(id, group);
  }
  const collisions = [...idGroups.entries()].filter(([, controls]) => controls.length > 1);
  if (collisions.length) {
    const details = collisions.map(([id, controls]) => ({
      proposed_id: id,
      controls: controls.map((control) => ({
        source_path: control.source_path,
        source_line: control.source_line,
        surface: control.surface,
        tag: control.tag,
        label: control.label,
        selector: selectorFor(control),
      })),
    }));
    throw new Error(`Ambiguous ID-less touchpoints require data-touchpoint-id annotations:\n${JSON.stringify(details, null, 2)}`);
  }

  const commandBoundary = JSON.parse(readText(commandBoundaryPath));
  if (!commandBoundary.ok) throw new Error(`${commandBoundaryPath} contains command-boundary violations.`);
  const routeEffects = new Map(
    (commandBoundary.route_usages || [])
      .filter((usage) => usage.normalized_route)
      .map((usage) => [usage.normalized_route, usage.contract_effect || ""]),
  );
  const overlay = loadOverlay();
  const staticOverrides = overlay.static_overrides || {};
  const staticAuditRuns = overlay.static_audit_runs || [];
  const focusedEvidenceGroups = overlay.focused_evidence_groups || [];
  const jsFiles = collectJsFiles();
  const scriptAnalyses = jsFiles.map((path) => ({ path, analysis: analyzeScriptAsset(path) }));
  const bindingsByFile = new Map(jsFiles.map((path) => [path, collectEventBindings(path)]));
  const scriptSources = jsFiles.map((path) => ({ path, source: readText(path) }));
  const browserTests = recursiveFiles(join(repoRoot, "tests", "webview"), (path) => /test_webview_browser.*\.py$/i.test(path))
    .map((path) => ({ path: repoRelative(path), source: readText(path) }));
  const smokeReconciliation = browserEvidenceInventory(browserTests);

  const records = staticControls.map((control) => {
    const id = touchpointId(control);
    const commandControl = matchingCommandControl(control, commandBoundary.controls || []);
    const action = actionFor(control, commandControl, routeEffects);
    const override = staticOverrides[id] || {};
    const safety = override.classification || defaultSafety(control, action);
    const references = browserReferences(control, browserTests);
    const sourceEvidence = sourceEvidenceFor(control, scriptAnalyses, bindingsByFile, scriptSources);
    const audit = auditForStaticRecord({ id, control, safety, references, override, staticAuditRuns, focusedEvidenceGroups });
    return {
      touchpoint_id: id,
      instance_count: 1,
      origin: "static_control",
      surface: { page: control.surface, panel: null, dialog: control.surface === "settings-save-dialog" ? "settings-save-review" : null },
      label: control.label,
      locator: { dom_id: control.id || null, selector: selectorFor(control), tag: control.tag, role: control.role || null },
      source: sourceEvidence,
      bindings: sourceEvidence
        .filter((source) => source.handler)
        .map((source) => ({ event: source.event, handler: source.handler, delegated_by: source.path, scope: source.binding_scope })),
      action,
      conditions: {
        visibility: control.conditions,
        enabled: Object.hasOwn(control.attrs, "disabled") ? ["authored disabled"] : [],
        configuration: control.finite_values,
      },
      classification: safety,
      expected_transition: override.expected_transition || expectedTransition(action),
      required_evidence: override.required_evidence || requiredEvidence(action),
      audit,
    };
  });

  const recordIds = new Set(records.map((record) => record.touchpoint_id));
  const orphanOverrides = Object.keys(staticOverrides).filter((id) => !recordIds.has(id));
  if (orphanOverrides.length) throw new Error(`Orphan static touchpoint evidence: ${orphanOverrides.join(", ")}`);
  const knownSurfaces = new Set(staticControls.map((control) => control.surface));
  const claimedSurfaces = new Map();
  const broadExceptionIds = new Set();
  for (const run of staticAuditRuns) {
    if (!run.run_id || !(run.surfaces || []).length || !(run.tests || []).length) {
      throw new Error(`Static audit run is missing run_id, surfaces, or tests: ${JSON.stringify(run)}`);
    }
    for (const path of run.tests) {
      if (!existsSync(join(repoRoot, path))) throw new Error(`Static audit run ${run.run_id} references missing test: ${path}`);
    }
    for (const surface of run.surfaces) {
      if (!knownSurfaces.has(surface)) throw new Error(`Static audit run ${run.run_id} references unknown surface: ${surface}`);
      if (claimedSurfaces.has(surface)) {
        throw new Error(`Static audit surface ${surface} is claimed by both ${claimedSurfaces.get(surface)} and ${run.run_id}`);
      }
      claimedSurfaces.set(surface, run.run_id);
    }
    for (const id of Object.keys(run.exceptions || {})) {
      broadExceptionIds.add(id);
      if (!recordIds.has(id)) throw new Error(`Static audit run ${run.run_id} has orphan exception: ${id}`);
      const record = records.find((item) => item.touchpoint_id === id);
      if (!(run.surfaces || []).includes(record.surface.page)) {
        throw new Error(`Static audit run ${run.run_id} exception ${id} is outside its surfaces.`);
      }
    }
    for (const group of run.exception_groups || []) {
      if (!group.status || !group.blocker || !(group.touchpoint_ids || []).length) {
        throw new Error(`Static audit run ${run.run_id} has an incomplete exception group: ${JSON.stringify(group)}`);
      }
      if (!allowedDispositionCategories.has(group.reason_category)) {
        throw new Error(`Static audit run ${run.run_id} exception group lacks a supported reason_category: ${JSON.stringify(group)}`);
      }
      for (const id of group.touchpoint_ids) {
        broadExceptionIds.add(id);
        if (!recordIds.has(id)) throw new Error(`Static audit run ${run.run_id} has orphan grouped exception: ${id}`);
        const record = records.find((item) => item.touchpoint_id === id);
        if (!(run.surfaces || []).includes(record.surface.page)) {
          throw new Error(`Static audit run ${run.run_id} grouped exception ${id} is outside its surfaces.`);
        }
      }
    }
  }
  const focusedIds = new Set();
  for (const group of focusedEvidenceGroups) {
    if (!group.evidence_id || !(group.tests || []).length || !(group.evidence || []).length || !(group.touchpoint_ids || []).length) {
      throw new Error(`Focused evidence group is incomplete: ${JSON.stringify(group)}`);
    }
    for (const path of group.tests) {
      if (!existsSync(join(repoRoot, path))) throw new Error(`Focused evidence ${group.evidence_id} references missing test: ${path}`);
    }
    for (const id of group.touchpoint_ids) {
      if (!recordIds.has(id)) throw new Error(`Focused evidence ${group.evidence_id} has orphan touchpoint: ${id}`);
      if (!broadExceptionIds.has(id)) throw new Error(`Focused evidence ${group.evidence_id} must supersede a traceable broad-census non-pass: ${id}`);
      if (focusedIds.has(id)) throw new Error(`Focused evidence overlaps on touchpoint: ${id}`);
      focusedIds.add(id);
    }
  }

  for (const family of [...(overlay.generated_families || []), ...(overlay.native_families || [])]) {
    if (!family.touchpoint_id || !family.classification?.status || !family.audit?.status || !Number.isInteger(family.instance_count) || family.instance_count < 1) {
      throw new Error(`Family record is missing required identity/classification/audit fields: ${JSON.stringify(family)}`);
    }
    validateAuditResult(family.audit, `family ${family.touchpoint_id}`);
    if (family.audit.status !== "passed" && !allowedDispositionCategories.has(family.audit.reason_category)) {
      throw new Error(`Family ${family.touchpoint_id} lacks a supported reason_category.`);
    }
    if (recordIds.has(family.touchpoint_id)) throw new Error(`Duplicate touchpoint ID: ${family.touchpoint_id}`);
    recordIds.add(family.touchpoint_id);
    records.push(family);
  }

  for (const record of records) {
    record.disposition = dispositionForRecord(record);
    record.control_identity = stableControlIdentity(record);
    record.evidence_state = record.audit.status;
    record.test_owner = {
      owner: record.disposition.owner,
      tests: record.disposition.test_references,
    };
  }

  records.sort((left, right) => left.touchpoint_id.localeCompare(right.touchpoint_id));
  const statusCounts = {};
  const auditCounts = {};
  const auditInstanceCounts = {};
  const originCounts = {};
  const originInstanceCounts = {};
  const dispositionCategoryCounts = {};
  const dispositionCategoryInstanceCounts = {};
  const closureClasses = [
    "automated_passed",
    "automated_but_failing",
    "legitimately_blocked",
    "manual_native_only",
    "intentionally_excluded",
    "stale_entries_removed",
    "unexplained_gaps",
  ];
  const closureClassCounts = Object.fromEntries(closureClasses.map((value) => [value, 0]));
  const closureClassInstanceCounts = Object.fromEntries(closureClasses.map((value) => [value, 0]));
  let totalTouchpointInstances = 0;
  for (const record of records) {
    statusCounts[record.classification.status] = (statusCounts[record.classification.status] || 0) + 1;
    auditCounts[record.audit.status] = (auditCounts[record.audit.status] || 0) + 1;
    originCounts[record.origin] = (originCounts[record.origin] || 0) + 1;
    const instanceCount = record.instance_count || 1;
    totalTouchpointInstances += instanceCount;
    originInstanceCounts[record.origin] = (originInstanceCounts[record.origin] || 0) + instanceCount;
    auditInstanceCounts[record.audit.status] = (auditInstanceCounts[record.audit.status] || 0) + instanceCount;
    dispositionCategoryCounts[record.disposition.category] = (dispositionCategoryCounts[record.disposition.category] || 0) + 1;
    dispositionCategoryInstanceCounts[record.disposition.category] = (dispositionCategoryInstanceCounts[record.disposition.category] || 0) + instanceCount;
    closureClassCounts[record.disposition.closure_class] += 1;
    closureClassInstanceCounts[record.disposition.closure_class] += instanceCount;
  }
  const unclassified = records.filter((record) => !record.classification?.status);
  const authoredRecords = records.filter((record) => record.origin === "static_control");
  const authoredAuditStates = ["passed", "failed", "flaky", "blocked", "skipped", "not_run"];
  const authoredAuditCounts = Object.fromEntries(authoredAuditStates.map((value) => [value, 0]));
  const authoredClosureCounts = Object.fromEntries(closureClasses.map((value) => [value, 0]));
  for (const record of authoredRecords) {
    authoredAuditCounts[record.audit.status] += 1;
    authoredClosureCounts[record.disposition.closure_class] += 1;
  }
  const authoredAuditTotal = Object.values(authoredAuditCounts).reduce((total, value) => total + value, 0);
  const authoredClosureTotal = Object.values(authoredClosureCounts).reduce((total, value) => total + value, 0);
  if (authoredRecords.length !== staticControls.length || authoredAuditTotal !== staticControls.length || authoredClosureTotal !== staticControls.length) {
    throw new Error(`Authored-control reconciliation failed: source=${staticControls.length}, ledger=${authoredRecords.length}, audit=${authoredAuditTotal}, disposition=${authoredClosureTotal}.`);
  }
  const staticControlsBySurface = {};
  for (const control of staticControls) {
    staticControlsBySurface[control.surface] = (staticControlsBySurface[control.surface] || 0) + 1;
  }
  return {
    schema_version: "webview_touchpoint_ledger.v2",
    generated_by: "ops/scripts/dev/generate-webview-touchpoint-ledger.mjs",
    source_index: repoRelative(webviewIndexPath),
    auxiliary_static_pages: auxiliaryStaticPages.map((page) => page.path),
    evidence_overlay: evidencePath,
    command_boundary_report: commandBoundaryPath,
    inventory_reconciliation: {
      dom: domReconciliation,
      browser_evidence: smokeReconciliation,
      authored_controls: {
        source_control_rows: staticControls.length,
        ledger_control_rows: authoredRecords.length,
        evidence_state_rows: authoredAuditTotal,
        disposition_rows: authoredClosureTotal,
        exact_match: true,
      },
    },
    scope_note: "Static controls come from the backend-rendered index selector contract. Runtime-generated and Tauri-native controls are curated as families. Audit status is per touchpoint; source/reference evidence is not promoted to physical activation without an explicit curated result.",
    counts: {
      total: records.length,
      total_records: records.length,
      total_touchpoint_instances: totalTouchpointInstances,
      static_controls: staticControls.length,
      main_static_controls: mainStaticControls.length,
      auxiliary_static_controls: auxiliaryStaticControls.length,
      id_backed_static_controls: staticControls.filter((control) => control.id).length,
      semantic_static_controls: staticControls.filter((control) => !control.id).length,
      static_controls_by_surface: staticControlsBySurface,
      by_origin: originCounts,
      by_origin_instances: originInstanceCounts,
      by_classification: statusCounts,
      by_audit_status: auditCounts,
      by_audit_status_instances: auditInstanceCounts,
      authored_controls_by_audit_status: authoredAuditCounts,
      by_disposition_category: dispositionCategoryCounts,
      by_disposition_category_instances: dispositionCategoryInstanceCounts,
      by_closure_class: closureClassCounts,
      by_closure_class_instances: closureClassInstanceCounts,
      authored_controls_by_closure_class: authoredClosureCounts,
      unclassified: unclassified.length,
    },
    records,
  };
}

const args = parseArgs(process.argv.slice(2));
try {
  const ledger = buildLedger();
  if (ledger.counts.unclassified !== 0) throw new Error(`Touchpoint ledger has ${ledger.counts.unclassified} unclassified record(s).`);
  if (ledger.counts.by_closure_class.unexplained_gaps !== 0 || ledger.counts.by_closure_class_instances.unexplained_gaps !== 0) {
    throw new Error(`Touchpoint ledger has unexplained evidence gaps: ${ledger.counts.by_closure_class.unexplained_gaps} record(s), ${ledger.counts.by_closure_class_instances.unexplained_gaps} instance(s).`);
  }
  process.exitCode = writeOrCheckJson(outputPath, ledger, args.check);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
