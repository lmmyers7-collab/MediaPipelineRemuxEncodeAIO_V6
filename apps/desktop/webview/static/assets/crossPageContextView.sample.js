// crossPageContextView.sample.js
// Split child of crossPageContextView.js — owns the cross-page sample-correlation
// engine and the validation-template render.  No mutation, no API calls.
//
// Loaded by index.html immediately BEFORE crossPageContextView.js so the parent
// IIFE can read window.__crossPageSampleModule, call the factory, then delete
// the stash.  After load, zero extra globals remain.
//
// Diagnostics lookups (diagnosticsSourceLines, diagnosticsSeverityForLine) are
// resolved at call time via window.mediaPipelineDiagnosticsView — no injection.
// All other shared utilities are injected by the parent factory call.

(function () {
  "use strict";

  function createCrossPageSampleModule({
    appendCells,
    byId,
    clearRows,
    crossPageCompletedOutput,
    crossPageCompletedSource,
    crossPageLeaf,
    crossPageNormalizePath,
    crossPagePathLooksAbsolute,
    crossPagePendingDestination,
    crossPagePendingLocal,
    crossPagePendingSource,
    crossPageQueueRuntimeOutput,
    crossPageQueueSource,
    crossPageRowLabel,
    crossPageRows,
    makeRowSelectable,
    setText,
    updateTableStatusLegend,
  }) {

    // -------------------------------------------------------------------------
    // Sample seed construction
    // -------------------------------------------------------------------------

    function crossPageSampleAddSeed(seeds, seen, kind, label, row, index = -1, selected = false) {
      if (!row || typeof row !== "object") return;
      const pathSpecs = [];
      const addPath = (role, value) => {
        const path = String(value || "").trim();
        if (!path) return;
        const normalized = crossPageNormalizePath(path);
        const leaf = crossPageLeaf(path).toLowerCase();
        if (!normalized && !leaf) return;
        pathSpecs.push({ role, path, normalized, leaf, pathLike: crossPagePathLooksAbsolute(path) });
      };
      if (kind === "Queue") {
        addPath("source", crossPageQueueSource(row));
        addPath("runtime output", crossPageQueueRuntimeOutput(row));
      } else if (kind === "Completed") {
        addPath("source", crossPageCompletedSource(row));
        addPath("output", crossPageCompletedOutput(row));
      } else if (kind === "Pending Publish") {
        addPath("source", crossPagePendingSource(row));
        addPath("destination", crossPagePendingDestination(row));
        addPath("parked payload", crossPagePendingLocal(row));
      }
      if (!pathSpecs.length) return;
      const signature = [kind, label, index, ...pathSpecs.map((item) => `${item.role}:${item.normalized || item.leaf}`)].join("|");
      if (seen.has(signature)) return;
      seen.add(signature);
      seeds.push({
        kind,
        label,
        row,
        index,
        selected: Boolean(selected),
        paths: pathSpecs,
        display: crossPageRowLabel(row, kind === "Pending Publish" ? "pending" : kind.toLowerCase()) || label,
      });
    }

    function crossPageSampleSeedRows(context = {}) {
      const queueRows = crossPageRows(context.queue || {});
      const completedRows = crossPageRows(context.completed || {});
      const pendingRows = crossPageRows(context.pending || {});
      const seeds = [];
      const seen = new Set();
      const selectedQueue = typeof window.getSelectedQueueRow === "function" ? window.getSelectedQueueRow() : null;
      const completedView = window.mediaPipelineCompletedView || {};
      const selectedCompleted = typeof completedView.getSelectedCompletedRow === "function" ? completedView.getSelectedCompletedRow() : null;
      const selectedPending = typeof window.getSelectedPendingRow === "function" ? window.getSelectedPendingRow() : null;
      crossPageSampleAddSeed(seeds, seen, "Queue", "selected Queue row", selectedQueue, queueRows.indexOf(selectedQueue), true);
      crossPageSampleAddSeed(seeds, seen, "Completed", "selected Completed row", selectedCompleted, completedRows.indexOf(selectedCompleted), true);
      crossPageSampleAddSeed(seeds, seen, "Pending Publish", "selected Pending row", selectedPending, pendingRows.indexOf(selectedPending), true);
      completedRows.slice(0, 5).forEach((row, index) => crossPageSampleAddSeed(seeds, seen, "Completed", "recent Completed row", row, index, false));
      queueRows.slice(0, 5).forEach((row, index) => crossPageSampleAddSeed(seeds, seen, "Queue", "visible Queue row", row, index, false));
      pendingRows.slice(0, 5).forEach((row, index) => crossPageSampleAddSeed(seeds, seen, "Pending Publish", "visible Pending row", row, index, false));
      return seeds.slice(0, 16);
    }

    // -------------------------------------------------------------------------
    // Match collection
    // -------------------------------------------------------------------------

    function crossPageSampleAddMatch(matches, seen, page, strength, field, value, note = "") {
      const text = String(value || "").trim();
      if (!text) return;
      const key = `${page}|${strength}|${field}|${crossPageNormalizePath(text) || text.toLowerCase()}|${note}`;
      if (seen.has(key)) return;
      seen.add(key);
      matches.push({ page, strength, field, value: text, note });
    }

    function crossPageSampleCollectPageMatches(matches, seen, seed, page, rows, fieldGetters) {
      const exactKeys = new Set(seed.paths.map((item) => item.normalized).filter(Boolean));
      const leafKeys = new Set(seed.paths.map((item) => item.leaf).filter(Boolean));
      (Array.isArray(rows) ? rows : []).slice(0, 500).forEach((row) => {
        fieldGetters.forEach(([field, getter]) => {
          const value = getter(row);
          const normalized = crossPageNormalizePath(value);
          const leaf = crossPageLeaf(value).toLowerCase();
          if (normalized && exactKeys.has(normalized)) {
            crossPageSampleAddMatch(matches, seen, page, "exact", field, value, "Exact normalized path match.");
          } else if (leaf && leafKeys.has(leaf)) {
            crossPageSampleAddMatch(matches, seen, page, "advisory", field, value, "Filename-only match; compare folders before trusting it.");
          }
        });
      });
    }

    function crossPageSampleCollectDiagnosticsMatches(matches, seen, seed, diagnostics) {
      const view = window.mediaPipelineDiagnosticsView || {};
      const sourceLines = typeof view.diagnosticsSourceLines === "function"
        ? view.diagnosticsSourceLines(diagnostics || {})
        : [];
      const exactKeys = seed.paths.map((item) => item.normalized).filter((item) => item && item.length > 8);
      const leafKeys = seed.paths.map((item) => item.leaf).filter((item) => item && item.length > 3);
      sourceLines.slice(-250).forEach((entry) => {
        const source = entry?.source || "Diagnostics";
        const line = String(entry?.line || "");
        const normalizedLine = crossPageNormalizePath(line);
        const lowerLine = line.toLowerCase();
        const exactHit = exactKeys.find((key) => normalizedLine.includes(key));
        if (exactHit) {
          crossPageSampleAddMatch(matches, seen, "Diagnostics", "exact", source, line.slice(0, 240), "Exact path text appears in diagnostics.");
          return;
        }
        const leafHit = leafKeys.find((key) => lowerLine.includes(key));
        if (leafHit) {
          crossPageSampleAddMatch(matches, seen, "Diagnostics", "advisory", source, line.slice(0, 240), "Filename text appears in diagnostics; not durable proof.");
        }
      });
    }

    // -------------------------------------------------------------------------
    // Evidence scoring
    // -------------------------------------------------------------------------

    function crossPageSampleEvidenceForSeed(seed, context = {}) {
      const matches = [];
      const seen = new Set();
      crossPageSampleCollectPageMatches(matches, seen, seed, "Queue", crossPageRows(context.queue || {}), [
        ["source", crossPageQueueSource],
        ["runtime output", crossPageQueueRuntimeOutput],
      ]);
      crossPageSampleCollectPageMatches(matches, seen, seed, "Completed", crossPageRows(context.completed || {}), [
        ["source", crossPageCompletedSource],
        ["output", crossPageCompletedOutput],
      ]);
      crossPageSampleCollectPageMatches(matches, seen, seed, "Pending Publish", crossPageRows(context.pending || {}), [
        ["source", crossPagePendingSource],
        ["destination", crossPagePendingDestination],
        ["parked payload", crossPagePendingLocal],
      ]);
      crossPageSampleCollectDiagnosticsMatches(matches, seen, seed, context.diagnostics || {});
      const exactPages = new Set(matches.filter((item) => item.strength === "exact").map((item) => item.page));
      const advisoryPages = new Set(matches.filter((item) => item.strength === "advisory").map((item) => item.page));
      const hasCompleted = exactPages.has("Completed");
      const hasQueue = exactPages.has("Queue");
      const hasPending = exactPages.has("Pending Publish");
      const hasDiagnostics = exactPages.has("Diagnostics") || advisoryPages.has("Diagnostics");
      let proofStrength = "No evidence";
      let status = "unknown";
      if (hasCompleted && (hasQueue || hasPending || hasDiagnostics)) {
        proofStrength = "Strong exact path trace";
        status = "match";
      } else if (exactPages.size >= 2) {
        proofStrength = "Exact path trace";
        status = "match";
      } else if (exactPages.size === 1) {
        proofStrength = "Partial exact proof";
        status = "warning";
      } else if (advisoryPages.size) {
        proofStrength = "Filename-only advisory";
        status = "changed";
      }
      const evidence = matches.slice(0, 8).map((item) => `${item.page} ${item.strength} ${item.field}: ${item.value}`).join(" | ") || `Trace key: ${seed.paths.map((item) => `${item.role}=${item.path}`).join("; ")}`;
      const nextStep = !matches.length
        ? "No cross-page evidence for this sample is visible in loaded payloads. Refresh and inspect the owning page before accepting or rerunning it."
        : !hasCompleted
          ? "Completed output/sidecar proof is not exact-matched yet. Inspect Completed after the run before treating this sample as accepted."
          : hasPending
            ? "Pending Publish evidence is visible. Compare parked/drain proof before final acceptance."
            : hasDiagnostics
              ? "Diagnostics evidence is visible. Read bounded logs/ActiveJobs, then compare Completed output and sidecar proof."
              : "Compare Completed route, output, sidecar, size, subtitle/audio, and any Pending Publish state before accepting the sample.";
      return {
        seed,
        proofStrength,
        status,
        exactPages,
        advisoryPages,
        matches,
        evidence,
        nextStep,
      };
    }

    function crossPageSampleRows(context = {}) {
      const rows = crossPageSampleSeedRows(context).map((seed) => crossPageSampleEvidenceForSeed(seed, context));
      const statusWeight = { match: 0, warning: 1, changed: 2, unknown: 3 };
      return rows.sort((left, right) => {
        if (left.seed.selected !== right.seed.selected) return left.seed.selected ? -1 : 1;
        return (statusWeight[left.status] ?? 4) - (statusWeight[right.status] ?? 4);
      });
    }

    function crossPageSampleStatus(context = {}) {
      const rows = crossPageSampleRows(context);
      if (!rows.length) return "No samples";
      if (rows.some((row) => row.status === "match")) return "Trace candidates";
      if (rows.some((row) => row.status === "warning")) return "Partial proof";
      if (rows.some((row) => row.status === "changed")) return "Advisory only";
      return "No proof";
    }

    function crossPageValidationTemplateStatus(context = {}) {
      const rows = crossPageSampleRows(context);
      if (!rows.length) return "No sample";
      if (rows[0]?.status === "match") return "Template ready";
      if (rows[0]?.status === "warning") return "Partial proof";
      if (rows[0]?.status === "changed") return "Advisory proof";
      return "Needs sample";
    }

    // -------------------------------------------------------------------------
    // Validation template
    // -------------------------------------------------------------------------

    function crossPageSamplePathLines(sample) {
      const seed = sample?.seed || {};
      const paths = Array.isArray(seed.paths) ? seed.paths : [];
      if (!paths.length) return ["- No source/output path candidates found in the selected sample row."];
      return paths.map((item) => `- ${item.role}: ${item.path}`);
    }

    function crossPageValidationTemplateLines(context = {}) {
      const samples = crossPageSampleRows(context);
      const sample = samples[0] || null;
      if (!sample) {
        return [
          "Real-media validation log template:",
          "Status: no Queue, Completed, or Pending Publish sample row is loaded.",
          "Next step: load or refresh Queue/Completed/Pending Publish, select a real sample row, then compare route, output, sidecar, size, subtitle/audio, diagnostics, and pending-publish evidence.",
          "Mutation guardrail: this template is read-only and is not persisted by the WebView.",
        ];
      }
      const exactPages = Array.from(sample.exactPages || []).join(", ") || "none";
      const advisoryPages = Array.from(sample.advisoryPages || []).join(", ") || "none";
      const matchLines = Array.isArray(sample.matches) && sample.matches.length
        ? sample.matches.slice(0, 10).map((item) => `- ${item.page} ${item.strength} ${item.field}: ${item.value}`)
        : ["- No cross-page evidence matches are visible in loaded payloads."];
      return [
        "Real-media validation log template:",
        "Generated from loaded WebView payloads only. This is operator evidence, not backend acceptance, manifest mutation, or media policy.",
        "Persisted evidence status: use the backend-owned Sample Validation Record panel below to preview or append evidence-only JSONL; this template itself is read-only.",
        "",
        `Sample: ${sample.seed.kind}: ${sample.seed.display}${sample.seed.selected ? " (selected)" : ""}`,
        `Proof strength: ${sample.proofStrength}`,
        `Exact evidence pages: ${exactPages}`,
        `Filename-only advisory pages: ${advisoryPages}`,
        "",
        "Trace keys:",
        ...crossPageSamplePathLines(sample),
        "",
        "Observed cross-page evidence:",
        ...matchLines,
        "",
        "Operator checks to fill after processing:",
        "- Queue route/remux-vs-encode reason checked: [ ] yes [ ] no",
        "- FFmpeg/run log evidence matches route: [ ] yes [ ] no",
        "- Preferred-language subtitle/SRT behavior checked: [ ] yes [ ] no [ ] not applicable",
        "- Audio passthrough/transcode/default-language behavior checked: [ ] yes [ ] no [ ] not applicable",
        "- Completed output exists and opens from expected destination: [ ] yes [ ] no",
        "- Sidecar/manifest points at current output: [ ] yes [ ] no",
        "- Size-growth policy result reviewed: [ ] yes [ ] no",
        "- Pending Publish parked/drain proof reviewed: [ ] yes [ ] no [ ] not applicable",
        "- Diagnostics has no fresh unexplained failure for this source/output: [ ] yes [ ] no",
        "",
        "Operator decision:",
        "- [ ] Accept this sample as WebView-observed success",
        "- [ ] Hold for manual review",
        "- [ ] Rerun only through backend-owned controls",
        "- [ ] Escalate to external rollback/manual review for this workflow",
        "",
        `Next step from loaded evidence: ${sample.nextStep}`,
        "Mutation guardrail: this template does not save, accept, repair, rerun, drain, delete, publish, rewrite manifests, or touch media files.",
      ];
    }

    function crossPageSelectSample(item) {
      const seed = item?.seed;
      if (!seed) return;
      if (seed.kind === "Queue" && typeof window.selectQueueRow === "function") {
        window.selectQueueRow(seed.row);
        if (typeof window.showPage === "function") window.showPage("queue");
        return;
      }
      const completedView = window.mediaPipelineCompletedView || {};
      if (seed.kind === "Completed" && typeof completedView.selectCompletedRow === "function") {
        completedView.selectCompletedRow(seed.row);
        if (typeof window.showPage === "function") window.showPage("completed");
        return;
      }
      if (seed.kind === "Pending Publish" && typeof window.selectPendingRow === "function") {
        window.selectPendingRow(seed.row);
        if (typeof window.showPage === "function") window.showPage("pending");
      }
    }

    // -------------------------------------------------------------------------
    // Sample board renders
    // -------------------------------------------------------------------------

    function renderCrossPageSampleCorrelation(context = {}) {
      const rows = crossPageSampleRows(context || {});
      if (typeof setPanelStatus === "function") setPanelStatus("cross-page-sample-status", crossPageSampleStatus(context || {}));
      else setText("cross-page-sample-status", crossPageSampleStatus(context || {}));
      const tbody = byId("cross-page-sample-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No Queue, Completed, or Pending Publish sample rows are loaded for correlation.");
        updateTableStatusLegend("cross-page-sample-legend", tbody, "Sample evidence rows");
        return;
      }
      tbody.replaceChildren();
      rows.slice(0, 16).forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = item.status;
        appendCells(row, [
          `${item.seed.kind}: ${item.seed.display}${item.seed.selected ? " (selected)" : ""}`,
          item.proofStrength,
          item.evidence,
          item.nextStep,
        ]);
        makeRowSelectable(row, () => crossPageSelectSample(item), {
          selected: Boolean(item.seed.selected),
          label: `Review sample evidence ${item.seed.kind} ${item.seed.display}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("cross-page-sample-legend", tbody, "Sample evidence rows");
    }

    function renderCrossPageValidationTemplate(context = {}) {
      if (typeof setPanelStatus === "function") setPanelStatus("cross-page-validation-template-status", crossPageValidationTemplateStatus(context || {}));
      else setText("cross-page-validation-template-status", crossPageValidationTemplateStatus(context || {}));
      setText("cross-page-validation-template", crossPageValidationTemplateLines(context || {}).join("\n"));
    }

    // -------------------------------------------------------------------------
    // Factory return
    // -------------------------------------------------------------------------

    return {
      crossPageSampleRows,
      crossPageSampleStatus,
      crossPageSampleEvidenceForSeed,
      crossPageValidationTemplateStatus,
      crossPageValidationTemplateLines,
      renderCrossPageSampleCorrelation,
      renderCrossPageValidationTemplate,
    };
  }

  window.__crossPageSampleModule = { createCrossPageSampleModule };
})();
