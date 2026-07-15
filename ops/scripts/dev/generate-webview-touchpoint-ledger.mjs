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
const staticRoot = "apps/desktop/webview/static";
const expectedMainStaticControlCount = 967;
const auxiliaryStaticPages = [
  {
    path: "apps/desktop/webview/static/assets/pipelineLogWindow.html",
    surfaceFallback: "pipeline-log-window",
    expectedControls: 3,
  },
];

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
  if (control.id && candidate.id === control.id) return 1000;
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

function defaultAuditFor(safety, references) {
  if (safety.status === "destructive") {
    return {
      status: "skipped",
      tests: [],
      evidence: references,
      blocker: safety.reason,
    };
  }
  if (safety.status === "unreachable") {
    return {
      status: "blocked",
      tests: [],
      evidence: references,
      blocker: safety.reason,
    };
  }
  return {
    status: "not_run",
    tests: [],
    evidence: references,
    blocker: "No per-touchpoint physical activation result has been curated yet.",
  };
}

function auditForStaticRecord({ id, control, safety, references, override, staticAuditRuns }) {
  if (override.audit) return validateAuditResult(override.audit, `static override ${id}`);
  if (["destructive", "unreachable"].includes(safety.status)) return defaultAuditFor(safety, references);

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
    }, `static audit exception ${id}`);
  }
  return validateAuditResult({
    status: run.status || "passed",
    tests: run.tests || [],
    evidence: run.evidence || [],
    blocker: run.blocker || null,
    run_id: run.run_id,
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
  if (mainStaticControls.length !== expectedMainStaticControlCount) {
    throw new Error(`Expected ${expectedMainStaticControlCount} main WebView static controls, found ${mainStaticControls.length}.`);
  }
  const auxiliaryStaticControls = auxiliaryStaticPages.flatMap((page) => {
    const controls = collectHtmlControls(readText(page.path), {
      sourcePath: page.path,
      surfaceFallback: page.surfaceFallback,
    });
    if (controls.length !== page.expectedControls) {
      throw new Error(`Expected ${page.expectedControls} controls in ${page.path}, found ${controls.length}.`);
    }
    return controls;
  });
  const staticControls = [...mainStaticControls, ...auxiliaryStaticControls];

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
  const jsFiles = collectJsFiles();
  const scriptAnalyses = jsFiles.map((path) => ({ path, analysis: analyzeScriptAsset(path) }));
  const bindingsByFile = new Map(jsFiles.map((path) => [path, collectEventBindings(path)]));
  const scriptSources = jsFiles.map((path) => ({ path, source: readText(path) }));
  const browserTests = recursiveFiles(join(repoRoot, "tests", "webview"), (path) => /test_webview_browser.*\.py$/i.test(path))
    .map((path) => ({ path: repoRelative(path), source: readText(path) }));

  const records = staticControls.map((control) => {
    const id = touchpointId(control);
    const commandControl = matchingCommandControl(control, commandBoundary.controls || []);
    const action = actionFor(control, commandControl, routeEffects);
    const override = staticOverrides[id] || {};
    const safety = override.classification || defaultSafety(control, action);
    const references = browserReferences(control, browserTests);
    const sourceEvidence = sourceEvidenceFor(control, scriptAnalyses, bindingsByFile, scriptSources);
    const audit = auditForStaticRecord({ id, control, safety, references, override, staticAuditRuns });
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
      for (const id of group.touchpoint_ids) {
        if (!recordIds.has(id)) throw new Error(`Static audit run ${run.run_id} has orphan grouped exception: ${id}`);
        const record = records.find((item) => item.touchpoint_id === id);
        if (!(run.surfaces || []).includes(record.surface.page)) {
          throw new Error(`Static audit run ${run.run_id} grouped exception ${id} is outside its surfaces.`);
        }
      }
    }
  }

  for (const family of [...(overlay.generated_families || []), ...(overlay.native_families || [])]) {
    if (!family.touchpoint_id || !family.classification?.status || !family.audit?.status || !Number.isInteger(family.instance_count) || family.instance_count < 1) {
      throw new Error(`Family record is missing required identity/classification/audit fields: ${JSON.stringify(family)}`);
    }
    validateAuditResult(family.audit, `family ${family.touchpoint_id}`);
    if (recordIds.has(family.touchpoint_id)) throw new Error(`Duplicate touchpoint ID: ${family.touchpoint_id}`);
    recordIds.add(family.touchpoint_id);
    records.push(family);
  }

  records.sort((left, right) => left.touchpoint_id.localeCompare(right.touchpoint_id));
  const statusCounts = {};
  const auditCounts = {};
  const originCounts = {};
  const originInstanceCounts = {};
  let totalTouchpointInstances = 0;
  for (const record of records) {
    statusCounts[record.classification.status] = (statusCounts[record.classification.status] || 0) + 1;
    auditCounts[record.audit.status] = (auditCounts[record.audit.status] || 0) + 1;
    originCounts[record.origin] = (originCounts[record.origin] || 0) + 1;
    const instanceCount = record.instance_count || 1;
    totalTouchpointInstances += instanceCount;
    originInstanceCounts[record.origin] = (originInstanceCounts[record.origin] || 0) + instanceCount;
  }
  const unclassified = records.filter((record) => !record.classification?.status);
  return {
    schema_version: "webview_touchpoint_ledger.v1",
    generated_by: "ops/scripts/dev/generate-webview-touchpoint-ledger.mjs",
    source_index: repoRelative(webviewIndexPath),
    auxiliary_static_pages: auxiliaryStaticPages.map((page) => page.path),
    evidence_overlay: evidencePath,
    command_boundary_report: commandBoundaryPath,
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
      by_origin: originCounts,
      by_origin_instances: originInstanceCounts,
      by_classification: statusCounts,
      by_audit_status: auditCounts,
      unclassified: unclassified.length,
    },
    records,
  };
}

const args = parseArgs(process.argv.slice(2));
try {
  const ledger = buildLedger();
  if (ledger.counts.unclassified !== 0) throw new Error(`Touchpoint ledger has ${ledger.counts.unclassified} unclassified record(s).`);
  process.exitCode = writeOrCheckJson(outputPath, ledger, args.check);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
