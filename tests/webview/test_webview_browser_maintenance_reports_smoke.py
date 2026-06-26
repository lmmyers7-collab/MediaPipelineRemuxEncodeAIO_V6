from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_maintenance_reports_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function maintenanceReportsScript() {
          return `
          (async () => {
            const posts = [];
            const gets = [];
            const originalApiGet = window.apiGet;
            const originalApiPost = window.apiPost;
            if (typeof originalApiGet !== "function") throw new Error("missing apiGet");
            window.apiGet = async (path, options) => {
              const normalizedPath = String(path || "");
              gets.push({ path: normalizedPath, options: options || {} });
              return originalApiGet(path, options);
            };
            window.apiPost = async (path, body, options) => {
              const normalizedPath = String(path || "");
              if (normalizedPath.includes("/api/ui-preferences")) {
                return { ok: true, message: "UI preference persistence ignored by smoke harness." };
              }
              posts.push({ path: normalizedPath, body: body || {}, options: options || {} });
              if (normalizedPath.includes("/api/failures/lifecycle")) {
                const transition = String(body?.transition || "");
                const dryRun = body?.dry_run === true;
                const nextState = transition === "acknowledge"
                  ? "acknowledged"
                  : transition === "start_work"
                    ? "working"
                    : transition === "mark_resolved"
                      ? "resolved"
                      : transition === "reopen"
                        ? "reopened"
                        : "working";
                if (transition === "mark_resolved" && dryRun) {
                  return {
                    command: "failures.lifecycle",
                    ok: true,
                    severity: "info",
                    message: "Failure lifecycle transition preview ready.",
                    errors: [],
                    data: {
                      journal_key: body?.journal_key || "",
                      transition,
                      step_id: body?.step_id || "",
                      dry_run: true,
                      current_state: "working",
                      next_state: "resolved",
                      lifecycle_state: "resolved",
                      dry_run_fingerprint: "smoke-lifecycle-fingerprint",
                      blockers: [],
                      journal_path: "C:/State/Failures/ResolutionJournal/events.jsonl",
                      writes_failure_resolution_journal: false,
                      touches_media: false,
                      safe_next_action: "Dry-run preview only; confirm when operator evidence has been reviewed.",
                    },
                  };
                }
                if (transition === "mark_resolved" && body?.confirm_transition === true) {
                  return {
                    command: "failures.lifecycle",
                    ok: true,
                    severity: "info",
                    message: "Failure lifecycle transition recorded.",
                    errors: [],
                    data: {
                      journal_key: body?.journal_key || "",
                      transition,
                      step_id: body?.step_id || "",
                      dry_run: false,
                      current_state: "working",
                      next_state: "resolved",
                      lifecycle_state: "resolved",
                      dry_run_fingerprint: body?.dry_run_fingerprint || "",
                      blockers: [],
                      journal_path: "C:/State/Failures/ResolutionJournal/events.jsonl",
                      writes_failure_resolution_journal: true,
                      touches_media: false,
                      safe_next_action: "Refresh Reports and continue from the next active issue.",
                    },
                  };
                }
                return {
                  command: "failures.lifecycle",
                  ok: true,
                  severity: "info",
                  message: "Failure lifecycle transition recorded.",
                  errors: [],
                  data: {
                    journal_key: body?.journal_key || "",
                    transition,
                    step_id: body?.step_id || "",
                    dry_run: false,
                    current_state: "new",
                    next_state: nextState,
                    lifecycle_state: nextState,
                    dry_run_fingerprint: "",
                    blockers: [],
                    journal_path: "C:/State/Failures/ResolutionJournal/events.jsonl",
                    writes_failure_resolution_journal: true,
                    touches_media: false,
                    safe_next_action: "Continue from the selected failure playbook.",
                  },
                };
              }
              if (normalizedPath.includes("/api/failures/clear") && body?.dry_run === true) {
                return {
                  command: "failures.clear",
                  ok: true,
                  severity: "info",
                  message: "Failure marker clear preview found 2 marker(s).",
                  errors: [],
                  data: {
                    scope: body.scope,
                    dry_run: true,
                    markers: 0,
                    planned: (Array.isArray(body?.marker_paths) && body.marker_paths.length
                      ? body.marker_paths
                      : [
                        "C:/State/Failures/Markers/marker-1.json",
                        "C:/State/Failures/Markers/marker-2.json",
                      ]).map((path) => ({ path })),
                    skipped: [],
                    errors: [],
                    manifest_path: "",
                    archive_dir: "",
                    writes_failure_markers: false,
                    touches_media: false,
                    safe_next_action: "Dry-run preview only; confirm clear only after reviewing marker evidence.",
                  },
                };
              }
              if (normalizedPath.includes("/api/failures/clear") && body?.confirm_clear === true) {
                if (body?.scope === "all_markers") {
                  return {
                    command: "failures.clear",
                    ok: true,
                    severity: "info",
                    message: "Failure marker clear moved 2 marker(s).",
                    errors: [],
                    data: {
                      scope: body.scope,
                      dry_run: false,
                      markers: 2,
                      planned: [
                        { path: "C:/State/Failures/Markers/marker-1.json" },
                        { path: "C:/State/Failures/Markers/marker-2.json" },
                      ],
                      skipped: [],
                      errors: [],
                      manifest_path: "C:/State/Failures/ClearManifests/failure_clear.json",
                      archive_dir: "C:/State/Failures/ClearManifests/ClearedMarkers/failure_clear",
                      writes_failure_markers: true,
                      touches_media: false,
                      safe_next_action: "Failure markers were moved; rerun only after reviewing refreshed marker evidence.",
                    },
                  };
                }
                return {
                  command: "failures.clear",
                  ok: false,
                  severity: "error",
                  message: "maintenance/reports smoke captured row clear post without moving marker files.",
                  errors: ["smoke harness blocks marker movement"],
                  data: {
                    scope: body.scope,
                    dry_run: false,
                    markers: 0,
                    planned: [{ path: body?.marker_paths?.[0] || "" }],
                    skipped: [],
                    errors: ["smoke harness blocks marker movement"],
                    manifest_path: "C:/State/Failures/ClearManifests/failure_clear.json",
                    archive_dir: "C:/State/Failures/ClearManifests/ClearedMarkers/failure_clear",
                    writes_failure_markers: false,
                    touches_media: false,
                    safe_next_action: "Smoke harness captured the payload only.",
                  },
                };
              }
              if (normalizedPath.includes("/api/failures/archive-evidence") && body?.dry_run === true) {
                return {
                  command: "failures.archive_evidence",
                  ok: true,
                  severity: "info",
                  message: "Failure evidence archive preview found 3 evidence file(s).",
                  errors: [],
                  data: {
                    scope: "all_active",
                    dry_run: true,
                    include_markers: body?.include_markers === true,
                    include_reports: body?.include_reports === true,
                    planned: [
                      { kind: "marker", path: "C:/State/Failures/Markers/marker-1.json" },
                      { kind: "marker", path: "C:/State/Failures/Markers/marker-2.json" },
                      { kind: "report", path: "C:/Reports/Failures/round_failures_001.json" },
                    ],
                    moved: [],
                    skipped: [],
                    errors: [],
                    markers: 0,
                    reports: 0,
                    manifest_path: "C:/State/Failures/ClearManifests/failure_evidence_archive.json",
                    archive_dir: "C:/State/Failures/ClearManifests/ClearedEvidence/failure_evidence_archive",
                    dry_run_fingerprint: "smoke-archive-fingerprint",
                    writes_failure_evidence: false,
                    touches_media: false,
                    safe_next_action: "Review the archive preview, enter a reason, then confirm if the evidence should leave active triage.",
                  },
                };
              }
              if (normalizedPath.includes("/api/failures/archive-evidence") && body?.confirm_archive === true) {
                return {
                  command: "failures.archive_evidence",
                  ok: true,
                  severity: "info",
                  message: "Failure evidence archive moved 3 evidence file(s).",
                  errors: [],
                  data: {
                    scope: "all_active",
                    dry_run: false,
                    include_markers: body?.include_markers === true,
                    include_reports: body?.include_reports === true,
                    planned: [],
                    moved: [
                      { path: "C:/State/Failures/Markers/marker-1.json", archive_path: "C:/State/Failures/ClearManifests/ClearedEvidence/failure_evidence_archive/Markers/marker-1.json" },
                      { path: "C:/State/Failures/Markers/marker-2.json", archive_path: "C:/State/Failures/ClearManifests/ClearedEvidence/failure_evidence_archive/Markers/marker-2.json" },
                      { path: "C:/Reports/Failures/round_failures_001.json", archive_path: "C:/State/Failures/ClearManifests/ClearedEvidence/failure_evidence_archive/Reports/round_failures_001.json" },
                    ],
                    skipped: [],
                    errors: [],
                    markers: 2,
                    reports: 1,
                    manifest_path: "C:/State/Failures/ClearManifests/failure_evidence_archive.json",
                    archive_dir: "C:/State/Failures/ClearManifests/ClearedEvidence/failure_evidence_archive",
                    dry_run_fingerprint: body?.dry_run_fingerprint || "",
                    writes_failure_evidence: true,
                    touches_media: false,
                    safe_next_action: "Failure evidence was archived; refresh active failures before making retry decisions.",
                  },
                };
              }
              if (normalizedPath.includes("/api/audit/score-policy")) {
                return {
                  command: "audit.score_policy",
                  ok: true,
                  severity: "info",
                  message: "Audit score policy smoke payload captured.",
                  data: {
                    schema_version: "desktop_audit_score_policy_result.v2",
                    policy: body?.reset ? {} : body?.policy || {},
                  },
                };
              }
              if (normalizedPath.includes("/api/audit/start")) {
                return {
                  command: "audit.start",
                  ok: true,
                  severity: "info",
                  message: "Started audit via PID 24681.",
                  data: {
                    library_root: body?.library_root || "",
                    include_sidecars: Boolean(body?.include_sidecars),
                    pid: 24681,
                    launch_prep: ["audit runtime ready"],
                    logs: "stdout: audit.stdout.log",
                  },
                };
              }
              if (normalizedPath.includes("/api/audit/stop")) {
                return {
                  command: "audit.stop",
                  ok: true,
                  severity: "info",
                  message: "Audit stop recorded. Force-killed audit process tree (PID 24681).",
                  data: {
                    schema_version: "desktop_audit_stop_result.v1",
                    requested_scope: "audit",
                    job_kinds: ["audit"],
                    stopped_process_tree_count: 1,
                    audit_progress_status: "stopped",
                  },
                };
              }
              if (normalizedPath.includes("/api/diagnostics/open")) {
                return {
                  command: "diagnostics.open",
                  ok: true,
                  severity: "info",
                  message: "Opened diagnostics target " + (body?.target || ""),
                  data: {
                    target: body?.target || "",
                    opened_path: "C:/Reports/failures.txt",
                  },
                  request: body || {},
                };
              }
              return { ok: false, message: "maintenance/reports smoke blocks mutation posts" };
            };
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function visiblePage(page) {
              return Boolean(document.querySelector('[data-page-panel="' + page + '"]')?.classList.contains("is-visible"));
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function navigate(page) {
              const showPage = window.showPage || window.mediaPipelineAppLifecycle?.showPage;
              if (typeof showPage !== "function") throw new Error("missing navigation function showPage");
              showPage(page);
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 12000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : "") + "\\nState:\\n" + [
                "maintenanceStatus=" + text("maintenance-status"),
                "maintenanceReadiness=" + text("maintenance-readiness"),
                "reportTriage=" + text("report-triage"),
                "failureSummary=" + text("failure-summary"),
                "auditSummary=" + text("audit-preview-summary"),
                "posts=" + JSON.stringify(posts),
              ].join("\\n"));
            }
            function clickFirst(selector, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.click();
            }
            [
              "renderMaintenance",
              "renderReleaseDryRunResult",
              "renderReleasePackageProgress",
              "releasePackageProgressBars",
              "renderBackfillDryRunResult",
              "renderBackfillProgress",
              "backfillProgressBars",
              "renderMaintenanceDryRunHistory",
              "getCommandHistory",
              "appendCommandResult",
            ].forEach(requireFunction);
            [
              "renderReports",
              "renderFailurePreview",
              "renderAuditPreview",
              "renderAuditControls",
              "initReportsViewEvents",
            ].forEach((name) => {
              if (typeof window.mediaPipelineReportsView[name] !== "function") {
                throw new Error("missing Reports namespace helper " + name);
              }
            });
            [
              "setReleasePackageStatus",
              "renderReleasePackageInFlightProgress",
              "releasePackageResultStatus",
              "collectReleaseDryRunRequest",
              "collectReleaseBuildRequest",
              "releaseRequestSignature",
              "releaseBuildConfirmMessage",
              "releasePreviewMatchesCreate",
              "recordReleasePreviewResult",
            ].forEach((name) => {
              if (typeof window.mediaPipelineMaintenanceView[name] !== "function") {
                throw new Error("missing Maintenance namespace helper " + name);
              }
            });

            navigate("maintenance");
            await waitFor(
              () => visiblePage("maintenance") && !text("maintenance-readiness").includes("No maintenance readiness loaded."),
              "Maintenance health rendering",
            );
            requireText("release-package-status-strip", [
              "Plan status",
              "Build status",
              "Idle",
            ]);
            requireText("maintenance-readiness", [
              "Real-media validation boundary:",
              "Mutation guardrail:",
            ]);
            byId("release-build-force").checked = true;
            const previewRequest = window.mediaPipelineMaintenanceView.collectReleaseDryRunRequest();
            const buildRequest = window.mediaPipelineMaintenanceView.collectReleaseBuildRequest();
            if (previewRequest.force !== true || buildRequest.force !== true) {
              throw new Error("Preview and Create deployment requests must both include force=true when Replace existing destination is checked.");
            }
            if (window.mediaPipelineMaintenanceView.releaseRequestSignature(previewRequest) !== window.mediaPipelineMaintenanceView.releaseRequestSignature(buildRequest)) {
              throw new Error("Preview and Create deployment option signatures should match for visible operator options.");
            }
            const unmatchedConfirm = window.mediaPipelineMaintenanceView.releaseBuildConfirmMessage(buildRequest);
            if (!unmatchedConfirm.includes("NO matching successful Preview Deployment") || !unmatchedConfirm.includes("Rollback/readiness implication")) {
              throw new Error("Create confirmation did not surface missing preview/rollback context.\\n" + unmatchedConfirm);
            }
            window.mediaPipelineMaintenanceView.recordReleasePreviewResult(previewRequest, { ok: true, message: "Fixture preview matched Create options." });
            if (!window.mediaPipelineMaintenanceView.releasePreviewMatchesCreate(buildRequest)) {
              throw new Error("Create request should match the latest successful Preview Deployment options.");
            }
            clickFirst('#maintenance-rows tr[data-selectable-row="true"]', "maintenance row");
            requireText("maintenance-detail", [
              "Check:",
              "Dry-run impact:",
              "Guardrail:",
            ]);
            window.mediaPipelineMaintenanceView.renderReleaseDryRunResult({
              ok: true,
              command: "maintenance.release_dry_run",
              message: "Release dry run completed.",
              warnings: ["fixture release warning"],
              data: {
                dry_run: true,
                manifest_exists: false,
                zip_exists: false,
                destination_root: "C:/Temp/MediaPipeline_Deployable_DryRun",
                returncode: 0,
                elapsed_seconds: 1.25,
                command: "pwsh -File ops\\\\scripts\\\\release\\\\build.ps1 -DryRun",
                options: { force: true },
                release_progress: {
                  schema_version: "desktop_release_package_progress.v1",
                  status: "complete",
                  dry_run: true,
                  detail: "Release dry run completed; copy plan 12 file(s), excluded 3.",
                  updated_at: "2026-05-17T12:00:00",
                  steps: [
                    { key: "layout", label: "Layout", status: "complete", detail: "Destination planned." },
                    { key: "copy", label: "Copy plan", status: "complete", detail: "Dry-run copy plan reports 12 file(s) copied and 3 excluded." },
                    { key: "manifest", label: "Manifest", status: "skipped", detail: "Manifest write skipped by dry-run boundary." },
                    { key: "validate", label: "Validate", status: "complete", detail: "Release builder exited successfully." },
                    { key: "optional_smoke", label: "Optional smoke", status: "skipped", detail: "Verify/smoke is only planned in this WebView dry-run." },
                  ],
                  progress_bars: [{
                    id: "release_package",
                    label: "Release package",
                    mode: "stepped",
                    percent: 100,
                    status: "complete",
                    detail: "Release dry run completed; copy plan 12 file(s), excluded 3.",
                    source: "maintenance.release_dry_run",
                    updated_at: "2026-05-17T12:00:00",
                    stale: false,
                  }],
                },
                stdout: "Dry run only. No files copied.",
                stderr: "",
              },
            });
            requireText("release-dry-run-progress-bars", [
              "Release package",
              "100%",
              "source: maintenance.release_dry_run",
            ]);
            requireText("release-package-status-strip", [
              "Preview done with warnings",
              "Release dry run completed.",
              "Destination: C:/Temp/MediaPipeline_Deployable_DryRun",
              "Preview only; no release folder, manifest, or zip was written.",
            ]);
            requireText("release-dry-run-detail", [
              "Dry-run trust summary:",
              "Writes manifest: no",
              "Writes zip: no; preview is dry-run only",
              "Replace existing destination option: yes",
              "Guardrail:",
              "Real-media boundary:",
            ]);
            window.mediaPipelineMaintenanceView.setReleasePackageStatus(
              "build",
              "running",
              "Building",
              "Deployment package is being created through the backend release builder.",
            );
            window.mediaPipelineMaintenanceView.renderReleasePackageInFlightProgress(
              "release-build-progress-bars",
              "Deployment package build",
              "Build is still running; controls re-enable when the backend returns.",
              "maintenance.release_build",
            );
            requireText("release-package-status-strip", [
              "Building",
              "Deployment package is being created through the backend release builder.",
            ]);
            requireText("release-build-progress-bars", [
              "Deployment package build",
              "active",
              "source: maintenance.release_build",
            ]);
            window.mediaPipelineMaintenanceView.renderReleaseBuildResult({
              ok: true,
              command: "maintenance.release_build",
              message: "Deployment build completed.",
              warnings: [],
              data: {
                dry_run: false,
                writes_release_package: true,
                manifest_exists: true,
                zip_exists: true,
                destination_root: "C:/Temp/MediaPipeline_Deployable",
                manifest_path: "C:/Temp/MediaPipeline_Deployable/release_manifest.json",
                zip_path: "C:/Temp/MediaPipeline_Deployable.zip",
                returncode: 0,
                elapsed_seconds: 5.5,
                command: "pwsh -File ops\\\\scripts\\\\release\\\\build.ps1 -Verify",
                options: { include_tauri_preview_binary: true, force: true },
                release_progress: {
                  schema_version: "desktop_release_package_progress.v1",
                  status: "complete",
                  dry_run: false,
                  detail: "Deployment package written and verified.",
                  updated_at: "2026-05-17T12:01:00",
                  progress_bars: [{
                    id: "release_package",
                    label: "Deployment package",
                    mode: "stepped",
                    percent: 100,
                    status: "complete",
                    detail: "Deployment package written and verified.",
                    source: "maintenance.release_build",
                    updated_at: "2026-05-17T12:01:00",
                    stale: false,
                  }],
                },
                stdout: "Release package created.",
                stderr: "",
              },
            });
            requireText("release-package-status-strip", [
              "Build done",
              "Deployment build completed.",
              "Destination: C:/Temp/MediaPipeline_Deployable",
            ]);
            requireText("release-build-progress-bars", [
              "Deployment package",
              "100%",
              "source: maintenance.release_build",
            ]);
            requireText("release-build-detail", [
              "Deployment build summary:",
              "Writes release package: yes",
              "Manifest written: yes",
              "Zip written: yes",
              "Replace existing destination: yes",
            ]);
            window.mediaPipelineMaintenanceView.renderBackfillDryRunResult({
              ok: true,
              command: "maintenance.completed_backfill_dry_run",
              message: "Completed manifest backfill dry run completed.",
              data: {
                dry_run: true,
                writes_manifest: false,
                sidecars_ingested: 12,
                skipped_bad_json: 1,
                manifest_path: "C:/State/Completed/completed_jobs.jsonl",
                checkpoint_path: "C:/State/Completed/backfill_checkpoint.json",
                backfill_progress: {
                  schema_version: "desktop_maintenance_backfill_progress.v1",
                  status: "complete",
                  dry_run: true,
                  records_scanned: 13,
                  records_written: 0,
                  records_would_write: 12,
                  records_skipped: 1,
                  detail: "Backfill dry run scanned 13 record(s); would write 12; wrote 0.",
                  updated_at: "2026-05-17T12:00:00",
                  progress_bars: [{
                    id: "maintenance_backfill",
                    label: "Maintenance backfill",
                    mode: "determinate",
                    percent: 100,
                    status: "complete",
                    detail: "Backfill dry run scanned 13 record(s); would write 12; wrote 0.",
                    source: "maintenance.completed_backfill_dry_run",
                    updated_at: "2026-05-17T12:00:00",
                    stale: false,
                  }],
                },
                stdout: "Dry-run sidecar scan completed.",
              },
            });
            requireText("backfill-dry-run-progress-bars", [
              "Maintenance backfill",
              "100%",
              "source: maintenance.completed_backfill_dry_run",
            ]);
            requireText("backfill-dry-run-detail", [
              "Dry-run trust summary:",
              "Writes completed manifest: no",
              "Records scanned: 13",
              "Records would write: 12",
              "Records written: 0",
              "Sidecars ingested: 12",
              "Skipped bad JSON: 1",
              "Guardrail:",
            ]);
            window.mediaPipelineMaintenanceView.renderDependencyAtlasResult({
              ok: true,
              command: "maintenance.dependency_atlas",
              message: "Dependency atlas updated: 377 module(s), 34 domain(s), 42 HTML link(s) checked.",
              data: {
                dry_run: false,
                writes_dependency_atlas: true,
                writes_media: false,
                atlas_html: "C:/Repo/docs/generated/dependency-atlas/dependency-atlas.html",
                atlas_png: "C:/Repo/docs/generated/dependency-atlas/dependency-atlas.png",
                atlas_svg: "C:/Repo/docs/generated/dependency-atlas/dependency-atlas.svg",
                assets_dir: "C:/Repo/docs/generated/dependency-atlas/assets",
                summary_csv: "C:/Repo/docs/generated/dependency-atlas/assets/dependency_summary.csv",
                module_edges_csv: "C:/Repo/docs/generated/dependency-atlas/assets/dependency_module_edges.csv",
                modules: "377",
                domain_edges: "34",
                detail_diagrams: "18",
                html_links_checked: "42",
                returncode: 0,
                elapsed_seconds: 2.5,
                command: "python -m mediapipeline.tools.dev.generate_dependency_atlas",
                dependency_atlas_progress: {
                  schema_version: "desktop_dependency_atlas_progress.v1",
                  status: "complete",
                  detail: "Dependency atlas generated.",
                  updated_at: "2026-05-17T12:00:00",
                  progress_bars: [{
                    id: "dependency_atlas",
                    label: "Dependency atlas",
                    mode: "stepped",
                    percent: 100,
                    status: "complete",
                    detail: "Dependency atlas generated.",
                    source: "maintenance.dependency_atlas",
                    updated_at: "2026-05-17T12:00:00",
                    stale: false,
                  }],
                },
                stdout: "Dependency atlas generated.",
              },
            });
            requireText("dependency-atlas-progress-bars", [
              "Dependency atlas",
              "100%",
              "source: maintenance.dependency_atlas",
            ]);
            requireText("dependency-atlas-detail", [
              "Dependency atlas update summary:",
              "Writes dependency atlas artifacts: yes",
              "Writes media or pipeline state: no",
              "Stale state: no",
              "Open C:/Repo/docs/generated/dependency-atlas/dependency-atlas.html or C:/Repo/docs/generated/dependency-atlas/dependency-atlas.png",
              "Guardrail:",
              "Modules: 377",
            ]);
            window.mediaPipelineMaintenanceView.renderDependencyAtlasResult({
              ok: true,
              command: "maintenance.dependency_atlas",
              message: "Dependency atlas updated but stale.",
              data: {
                writes_dependency_atlas: true,
                writes_media: false,
                stale: true,
                atlas_html: "docs/generated/dependency-atlas/dependency-atlas.html",
                atlas_png: "docs/generated/dependency-atlas/dependency-atlas.png",
                dependency_atlas_progress: {
                  status: "stale",
                  progress_bars: [{
                    id: "dependency_atlas",
                    label: "Dependency atlas",
                    mode: "determinate",
                    percent: 100,
                    status: "stale",
                    detail: "Atlas is stale.",
                    stale: true,
                  }],
                },
              },
            });
            requireText("dependency-atlas-detail", ["Stale state: yes", "rerun Update Atlas before relying on these files"]);
            if (byId("dependency-atlas-status")?.dataset.state !== "stale") {
              throw new Error("Dependency atlas stale state should set data-state=stale.");
            }
            requireText("dependency-atlas-open-folder-button", ["Open Folder"]);
            window.appendCommandResult({
              command: "maintenance.release_dry_run",
              ok: true,
              severity: "info",
              message: "Release dry run completed.",
              data: { dry_run: true, manifest_exists: false, zip_exists: false, manifest_created: false, zip_created: false, returncode: 0, elapsed_seconds: 1.25 },
            });
            window.appendCommandResult({
              command: "maintenance.completed_backfill_dry_run",
              ok: true,
              severity: "info",
              message: "Completed manifest backfill dry run completed.",
              data: { dry_run: true, writes_manifest: false, sidecars_ingested: 12, skipped_bad_json: 1 },
            });
            window.appendCommandResult({
              command: "maintenance.dependency_atlas",
              ok: true,
              severity: "info",
              message: "Dependency atlas updated.",
              data: { writes_dependency_atlas: true, modules: "377", detail_diagrams: "18", html_links_checked: "42", returncode: 0, elapsed_seconds: 2.5 },
            });
            window.mediaPipelineMaintenanceView.renderMaintenanceDryRunHistory(window.getCommandHistory());
            requireText("maintenance-dry-run-history", [
              "Release dry run",
              "Completed manifest backfill dry run",
              "Dependency atlas",
              "377 module(s)",
            ]);

            navigate("reports");
            await waitFor(() => visiblePage("reports"), "Reports page visible");
            if (document.querySelector('[data-reports-tab="overview"]')) {
              throw new Error("Reports Overview tab should not be present.");
            }
            if (document.querySelector('[data-reports-tab="files"]')?.textContent.trim() !== "Locations") {
              throw new Error("Reports files tab key should render with the visible Locations label.");
            }
            if (document.querySelector('[data-reports-tab="failures"]')?.getAttribute("aria-selected") !== "true") {
              throw new Error("Reports Failures tab was not selected by default.");
            }
            const failureSourceMarkersControl = byId("failure-source-markers");
            if (!failureSourceMarkersControl) throw new Error("Reports failure marker source checkbox is missing.");
            if (failureSourceMarkersControl.checked !== true) {
              throw new Error("Reports failure marker source checkbox should be checked by default.");
            }
            const beforeMarkerRefreshGets = gets.length;
            await window.refreshAllNow();
            const markerRefreshGets = gets.slice(beforeMarkerRefreshGets).filter((entry) => entry.path.startsWith("/api/failures"));
            if (!markerRefreshGets.some((entry) => entry.path === "/api/failures?limit=100&source=markers")) {
              throw new Error("Default Reports failure refresh did not request active failure markers: " + JSON.stringify(markerRefreshGets));
            }
            failureSourceMarkersControl.checked = false;
            const beforeLatestRefreshGets = gets.length;
            await window.refreshAllNow();
            const latestRefreshGets = gets.slice(beforeLatestRefreshGets).filter((entry) => entry.path.startsWith("/api/failures"));
            if (!latestRefreshGets.some((entry) => entry.path === "/api/failures?limit=100")) {
              throw new Error("Unchecked Reports failure refresh did not request latest JSON: " + JSON.stringify(latestRefreshGets));
            }
            if (latestRefreshGets.some((entry) => entry.path.includes("source=markers"))) {
              throw new Error("Unchecked Reports failure refresh still requested marker source: " + JSON.stringify(latestRefreshGets));
            }
            failureSourceMarkersControl.checked = true;
            [
              "report-launch-handoff",
              "report-launch-handoff-status",
              "report-launch-handoff-action-status",
              "report-go-rerun-button",
              "report-go-audit-button",
              "report-go-diagnostics-button",
            ].forEach((id) => {
              if (byId(id)) throw new Error("removed Reports pre-launch DOM node is still present: " + id);
            });
            [
              "renderReportLaunchHandoff",
              "reportGoToCsvRerun",
              "reportGoToAuditLaunch",
              "reportGoToDiagnostics",
            ].forEach((name) => {
              if (typeof window.mediaPipelineReportsView[name] === "function") {
                throw new Error("removed Reports pre-launch helper is still exported: " + name);
              }
            });
            window.mediaPipelineReportsView.renderReports(
              {
                latest_paths: {
                  latest_failure_report: "C:/Reports/failures.txt",
                  latest_failure_json: "C:/Reports/failures.json",
                  latest_audit_csv: "C:/Reports/audit_summary.csv",
                  latest_priority_csv: "C:/Reports/audit_priority.csv",
                },
                warnings: [],
                audit_progress: {
                  status: "writing-reports",
                  processed_files: 10,
                  total_files: 10,
                  percent_complete: 100,
                  current_operation: "Writing CSV audit summary.",
                  report_stage: "write_csv",
                  report_step_index: 2,
                  report_step_total: 5,
                  report_completed_steps: ["classify", "write_json"],
                  latest_json_path: "C:/Reports/audit_summary.json",
                },
                progress_bars: [{
                  id: "audit_progress",
                  label: "Audit progress",
                  mode: "determinate",
                  percent: 100,
                  status: "active",
                  detail: "10 / 10 | Writing CSV audit summary.",
                  source: "audit_progress.json",
                  updated_at: "2026-05-17T12:00:00Z",
                }, {
                  id: "audit_reports",
                  label: "Audit reports",
                  mode: "stepped",
                  percent: 40,
                  status: "active",
                  detail: "2 / 5 | write csv | done: classify, write json",
                  source: "audit_progress.json",
                  updated_at: "2026-05-17T12:00:00Z",
                }],
              },
              {
                paths: {
                  failed_reports: "C:/Reports/Failures",
                  failed_markers: "C:/State/FailedMarkers",
                  audit_reports: "C:/Reports/Audit",
                  completed_manifest: "C:/State/Completed/completed_jobs.jsonl",
                  pending_push: "C:/PendingServerPush",
                  queue_snapshot: "C:/State/Progress/queue_snapshot.json",
                  active_jobs: "C:/State/ActiveJobs",
                },
              }
            );
            clickFirst('[data-reports-tab="audit"]', "Reports Audit tab");
            requireText("report-progress-summary", [
              "Audit status: writing-reports",
              "Report generation: 2 / 5 (write csv)",
              "Completed report steps: classify, write json",
              "Mutation guardrail:",
            ]);
            const reportFailureRow = {
              row_key: "fixture-failure-row-source-locked",
              source_json: "C:/Reports/failures.json",
              source_path: "C:/Source/Broken Movie.mkv",
              lookup_title: "Broken Movie",
              media_type: "movie",
              classification: "operator_required",
              error_code: "source_locked",
              stage: "source-stability",
              reason: "Source changed during probe.",
              suggested_action: "Wait for the source to stabilize before rerun.",
              suggested_rename: "",
              retry_count: 1,
              retry_limit: 3,
              recorded_at: "2026-05-14T22:00:00-04:00",
              artifact_path: "C:/Reports/source_locked.txt",
              repro_path: "C:/Source/Broken Movie.mkv",
              evidence_details: {
                schema_version: "desktop_failure_evidence_details.v1",
                structured: true,
                source: "video_stream_evidence",
                summary_lines: ["Video streams: source real=2, attached=0"],
                stream_rows: [
                  { source: "source", index: 0, ordinal: 0, codec: "hevc", width: 1920, height: 1080, attached_picture: false, label: "source v:0 hevc 1920x1080" },
                  { source: "source", index: 1, ordinal: 1, codec: "h264", width: 1280, height: 720, attached_picture: false, label: "source v:1 h264 1280x720" },
                ],
                proof_fields: [{ label: "Route", value: "encode" }],
              },
            };
            const reportFailureGroup = {
              schema_version: "desktop_failure_resolution_group.v1",
              group_key: "source_locked\u001fsource-stability\u001fmanual-review\u001freview-in-diagnostics",
              journal_key: "source_locked|source-stability|manual-review|review-in-diagnostics",
              status_label: "Needs operator",
              severity: "error",
              error_code: "source_locked",
              stage: "source-stability",
              owner: "Manual review",
              owner_page: "diagnostics",
              suggested_action: "Wait for the source to stabilize before rerun.",
              cause: "Source changed during probe.",
              safe_next_action: "Open Diagnostics and review the latest failure report before rerun.",
              row_count: 1,
              affected_row_keys: ["fixture-failure-row-source-locked"],
              affected_sources: ["Broken Movie"],
              sample_rows: [reportFailureRow],
              clearable_marker_paths: [],
              clearable_count: 0,
              marker_count: 0,
              blocking_count: 1,
              retryable_count: 0,
              operator_required_count: 1,
              permanent_count: 0,
              transient_count: 0,
              diagnostic_targets: [
                { label: "Read Latest Failure", target: "latest_failure_report" },
                { label: "Open Failure JSON", target: "latest_failure_json" },
                { label: "Open Failure Reports", target: "failed_reports" },
                { label: "Open Run Logs", target: "run_logs" },
                { label: "Open Failure Markers", target: "failed_markers" },
              ],
              primary_action: { kind: "open_owner_page", label: "Review in Diagnostics", page: "diagnostics", owner: "Manual review" },
              primary_action_label: "Review in Diagnostics",
              lifecycle_state: "new",
              lifecycle_label: "New",
              last_transition_at: "",
              operator_note: "",
              verification: {
                schema_version: "failure_resolution_verification.v1",
                active_marker_count: 0,
                active_failure_row_count: 1,
                blocking_count: 1,
                retryable_count: 0,
                clearable: false,
                safe_to_resolve: true,
                blockers: [],
              },
              playbook_steps: [
                { id: "review_evidence", label: "Review evidence", detail: "Confirm the source-lock evidence and last run log.", status: "current" },
                { id: "stabilize_source", label: "Stabilize source", detail: "Make sure the source file is no longer changing.", status: "not_started" },
                { id: "resolve_record", label: "Mark resolved", detail: "Confirm resolution after verification.", status: "not_started" },
              ],
              timeline: [],
              resolution_journal_path: "C:/State/Failures/ResolutionJournal/events.jsonl",
              available_transitions: [
                { transition: "acknowledge", label: "Acknowledge", preview_required: false, disabled: false },
                { transition: "start_work", label: "Start work", preview_required: false, disabled: false },
                { transition: "mark_resolved", label: "Mark resolved", preview_required: true, disabled: false },
              ],
            };
            const reportFailurePreview = {
              source: "C:/Reports/failures.json",
              source_kind: "latest_json",
              count: 1,
              operator_required_count: 1,
              permanent_count: 0,
              transient_count: 0,
              warnings: ["fixture failure warning"],
              resolution_summary: {
                schema_version: "desktop_failure_resolution.v1",
                status: "blocked",
                status_label: "Needs operator",
                source_kind: "latest_json",
                source_mode_label: "Latest failure JSON",
                refresh_state: "loaded",
                row_count: 1,
                group_count: 1,
                primary_group_key: reportFailureGroup.group_key,
                primary_owner: "Manual review",
                primary_action: reportFailureGroup.primary_action,
                primary_action_label: "Review in Diagnostics",
                safe_next_action: "Open Diagnostics and review the latest failure report before rerun.",
                blocking_count: 1,
                retryable_count: 0,
                clearable_count: 0,
                warning_count: 1,
                lifecycle_counts: { new: 1 },
                unacknowledged_count: 1,
                working_count: 0,
                waiting_backend_count: 0,
                ready_to_clear_count: 0,
                resolved_recently_count: 0,
              },
              resolution_groups: [reportFailureGroup],
              rows: [reportFailureRow],
            };
            window.mediaPipelineReportsView.renderFailurePreview(reportFailurePreview);
            const reportAuditPreview = {
              source: "C:/Reports/audit_priority.csv",
              priority_only: true,
              count: 1,
              high_priority_count: 1,
              rerun_count: 1,
              redownload_count: 0,
              review_count: 0,
              duplicate_group_count: 0,
              warnings: ["fixture audit warning"],
              rows: [{
                source_csv: "C:/Reports/audit_priority.csv",
                path: "C:/Outsource/TV/Serial Experiments Lain/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
                relative_path: "TV/Serial Experiments Lain/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
                lookup_title: "Serial Experiments Lain",
                media_type: "episode",
                effective_bucket: "RERUN_PIPELINE",
                priority_fix_level: "HIGH",
                priority_score: 95,
                primary_issue_code: "subtitle_missing_srt",
                primary_suggested_action: "Rerun pipeline for preferred-language SRT.",
                issue_messages: "Preferred-language SRT missing.",
              }],
            };
            window.mediaPipelineReportsView.renderAuditPreview(reportAuditPreview);
            const highScoreMarkerCodes = [
              "ffprobe-open-failed",
              "missing-video-stream",
              "missing-audio-stream",
              "audio-multiple-defaults",
              "audio-default-policy-mismatch",
              "subtitle-multiple-defaults",
              "audio-missing-explicit-default",
              "commentary-default-audio",
              "tx3g-extraction-failed",
              "bdpgs-ocr-failed",
              "vobsub-ocr-failed",
              "foreign-audio-no-subtitles",
              "foreign-audio-no-text-subtitles",
            ];
            const mediumScoreMarkerCodes = [
              "multiple-video-streams",
              "audio-track-titles-missing",
              "subtitle-track-titles-missing",
              "default-audio-language-unknown",
              "default-subtitle-language-unknown",
              "default-audio-may-transcode",
              "default-ass-subtitle",
              "ass-only-subtitles",
              "tx3g-only-subtitles",
              "tx3g-subtitles-extractable",
              "bdpgs-only-subtitles",
              "bdpgs-subtitles-ocr-candidate",
              "vobsub-only-subtitles",
              "vobsub-subtitles-ocr-candidate",
              "default-image-subtitle",
              "image-only-subtitles",
              "audio-language-tags-unknown",
              "subtitle-language-tags-unknown",
              "ambiguous-tv-naming",
            ];
            const auditIssueWeights = {};
            const auditDefaultIssueWeights = {};
            const auditScoreMarkers = [
              { type: "base", key: "redownload_bucket", label: "Redownload candidate bucket", applies_when: "Any effective issue has bucket REDOWNLOAD_CANDIDATE." },
              { type: "group_default", key: "high_issue", group: "high", label: "High issue-code marker default", applies_when: "Default score for high issue-code markers." },
            ];
            highScoreMarkerCodes.forEach((code) => {
              auditIssueWeights[code] = 90;
              auditDefaultIssueWeights[code] = 90;
              auditScoreMarkers.push({
                type: "issue_code",
                code,
                group: "high",
                label: "High issue: " + code,
                applies_when: "High issue-code marker " + code,
              });
            });
            auditScoreMarkers.push(
              { type: "base", key: "rerun_bucket", label: "Rerun pipeline bucket", applies_when: "Any remaining effective issue has bucket RERUN_PIPELINE." },
              { type: "group_default", key: "medium_issue", group: "medium", label: "Medium issue-code marker default", applies_when: "Default score for medium issue-code markers." }
            );
            mediumScoreMarkerCodes.forEach((code) => {
              auditIssueWeights[code] = 40;
              auditDefaultIssueWeights[code] = 40;
              auditScoreMarkers.push({
                type: "issue_code",
                code,
                group: "medium",
                label: "Medium issue: " + code,
                applies_when: "Medium issue-code marker " + code,
              });
            });
            auditIssueWeights["ffprobe-open-failed"] = 95;
            auditScoreMarkers.push(
              { type: "base", key: "review_bucket", label: "Review bucket", applies_when: "Any remaining effective issue has bucket REVIEW." },
              { type: "base", key: "fallback_issue", label: "Fallback issue marker", applies_when: "Any effective issue not matched by higher priority markers." },
              { type: "base", key: "redownload_bonus", label: "Redownload candidate bonus", applies_when: "Added once when a redownload issue is present." },
              { type: "base", key: "rerun_bonus", label: "Rerun pipeline bonus", applies_when: "Added once when a rerun issue is present." }
            );
            const reportAuditControls = {
              schema_version: "desktop_audit_controls.v1",
              score_policy: {
                schema_version: "desktop_audit_score_policy.v2",
                persisted: false,
                path: "C:/State/audit_score_policy.json",
                policy: {
                  redownload_bucket: 100,
                  high_issue: 90,
                  rerun_bucket: 60,
                  medium_issue: 40,
                  review_bucket: 20,
                  fallback_issue: 10,
                  redownload_bonus: 100,
                  rerun_bonus: 40,
                  issue_code_weights: auditIssueWeights,
                },
                defaults: {
                  redownload_bucket: 100,
                  high_issue: 90,
                  rerun_bucket: 60,
                  medium_issue: 40,
                  review_bucket: 20,
                  fallback_issue: 10,
                  redownload_bonus: 100,
                  rerun_bonus: 40,
                  issue_code_weights: auditDefaultIssueWeights,
                },
                markers: auditScoreMarkers,
              },
              ignore_manifest: {
                entry_count: 0,
                path: "C:/State/audit_ignore_manifest.json",
              },
            };
            window.mediaPipelineReportsView.renderAuditControls(reportAuditControls);
            clickFirst('[data-reports-tab="files"]', "Reports Locations tab");
            await waitFor(() => document.querySelector('[data-reports-tab="files"]')?.getAttribute("aria-selected") === "true", "Reports Locations tab selected");
            const reportPathOpenButton = document.querySelector('#report-path-rows button[data-open-diagnostics]');
            if (!reportPathOpenButton) throw new Error("Reports Locations did not render an Open button.");
            const beforeReportOpenPosts = posts.length;
            reportPathOpenButton.click();
            await waitFor(() => posts.length === beforeReportOpenPosts + 1, "Reports Locations diagnostics open post");
            await waitFor(() => text("report-open-history").includes("diagnostics.open"), "Reports recently opened history updated");
            if (!document.querySelector('#report-path-rows')?.textContent.includes("Opened diagnostics target")) {
              throw new Error("Reports path Open button did not show inline open feedback.");
            }
            requireText("report-triage", [
              "Failure JSON: present",
              "Audit CSV: present",
              "Failure rows: 1",
              "Audit rows: 1",
              "Mutation guardrail:",
            ]);
            requireText("report-investigation-checklist", [
              "Reports investigation checklist:",
              "Failure preview | Loaded",
              "Audit preview | Loaded",
              "Suggested investigation order:",
            ]);
            requireText("report-warning-rows", [
              "fixture failure warning",
              "fixture audit warning",
              "Diagnostics",
            ]);
            requireText("report-triage-band-detail", [
              "Next action:",
              "Action owner:",
              "Failure rows needing operator/permanent review: 1",
              "Audit rerun/redownload/high-priority candidates: 2",
            ]);
            requireText("failure-review-board", [
              "Review State",
              "Action needed",
              "Failed Rows",
              "Primary Stage",
              "Root Cause",
              "source_locked: 1",
              "Operator Holds",
              "Next Step",
              "Inspect holds",
            ]);
            requireText("failure-review-board-detail", [
              "Failure review board:",
              "Operator/permanent rows: 1",
              "source_locked",
              "Mutation guardrail:",
            ]);
            requireText("audit-preview-summary", [
              "Rows: 1",
              "High priority: 1",
              "Rerun: 1",
            ]);
            requireText("audit-review-board", [
              "Audit review board:",
              "Rerun rows: 1",
              "subtitle_missing_srt",
              "Mutation guardrail:",
            ]);
            clickFirst('[data-reports-tab="failures"]', "Reports Failures tab");
            if (document.querySelector('[data-reports-tab="failures"]')?.getAttribute("aria-selected") !== "true") {
              throw new Error("Reports Failures tab did not become selected.");
            }
            requireText("failure-resolution-summary-strip", [
              "Posture",
              "Needs operator",
              "Primary action",
              "Review in Diagnostics",
              "Blocking",
              "1",
              "Will retry",
              "0",
              "Clearable markers",
              "0",
              "Source mode",
              "Latest failure JSON",
            ]);
            requireText("failure-resolution-groups", [
              "Source changed during probe.",
              "Needs operator",
              "1 row",
              "Manual review",
              "Review in Diagnostics",
            ]);
            requireText("failure-detail", [
              "Why it stopped",
              "Status: Needs operator",
              "Cause: Source changed during probe.",
              "Stage: source-stability",
              "Code: source_locked",
              "Suggested resolution",
              "Owner: Manual review",
              "Primary action: Review in Diagnostics",
              "Suggested fix: Wait for the source to stabilize before rerun.",
              "Affected files",
              "Broken Movie",
              "Structured proof",
              "Video streams: source real=2, attached=0",
              "source v:0 hevc 1920x1080",
              "source v:1 h264 1280x720",
              "Evidence",
              "Clearable marker paths: 0",
              "Record file: C:/Reports/failures.json",
            ]);
            requireText("failure-rows", [
              "Needs operator",
              "Broken Movie",
              "Stage: source-stability",
              "Code: source_locked",
              "Class: operator_required",
              "Retry: Blocked (1/3)",
              "Marker: not active",
              "Video streams: source real=2, attached=0",
              "source v:0 hevc 1920x1080",
              "source v:1 h264 1280x720",
              "Manual review",
              "Wait for the source to stabilize before rerun.",
            ]);
            const failureRecordsPanel = document.getElementById("failure-all-records-disclosure");
            if (!failureRecordsPanel || failureRecordsPanel.tagName !== "SECTION") {
              throw new Error("failure records grid should be a visible section, not a hidden disclosure");
            }
            const failureRecordsWrap = document.querySelector("#failure-all-records-disclosure .failure-records-table-wrap");
            const failureRecordsRect = failureRecordsWrap?.getBoundingClientRect();
            if (!failureRecordsRect || failureRecordsRect.width < 200 || failureRecordsRect.height < 80) {
              throw new Error("failure records grid is not visibly rendered");
            }
            if (text("failure-rows").includes("Clear error") || text("failure-rows").includes("Open details")) {
              throw new Error("failure table still exposes row-level action copy");
            }
            if (text("failure-rows").includes("2026-05-14T22:00:00-04:00")) {
              throw new Error("failure table still shows the long recorded timestamp");
            }
            const failureCheckbox = document.querySelector('#failure-rows input[type="checkbox"]');
            if (!failureCheckbox) throw new Error("failure row multi-select checkbox missing");
            failureCheckbox.click();
            if (!document.querySelector('#failure-rows input[type="checkbox"]')?.checked) {
              throw new Error("failure row multi-select checkbox did not stay checked");
            }
            if (document.querySelector('#failure-rows button')) {
              throw new Error("failure rows should not render inline action buttons");
            }
            clickFirst('#failure-rows tr[data-row-key]', "failure row");
            requireText("failure-detail", [
              "Why it stopped",
              "Status: Needs operator",
              "Cause: Source changed during probe.",
              "Stage: source-stability",
              "Code: source_locked",
              "Suggested resolution",
              "Owner: Manual review",
              "Primary action: Review in Diagnostics",
              "Structured proof",
              "source v:0 hevc 1920x1080",
              "source v:1 h264 1280x720",
              "Evidence",
            ]);
            requireText("failure-lifecycle-strip", [
              "State",
              "New",
              "Last action",
              "None",
              "Resolution check",
              "Pass",
            ]);
            requireText("failure-playbook-steps", [
              "Review evidence | current | Confirm the source-lock evidence and last run log.",
              "Stabilize source | not started | Make sure the source file is no longer changing.",
              "Mark resolved | not started | Confirm resolution after verification.",
            ]);
            requireText("failure-verification-panel", [
              "Active markers",
              "0",
              "Failure rows",
              "1",
              "Safe to resolve",
              "Yes",
            ]);
            requireText("failure-timeline", ["No lifecycle events recorded."]);
            window.confirm = () => true;
            const originalRefreshAllForLifecycle = window.refreshAll;
            let lifecycleRefreshes = 0;
            window.refreshAll = async () => { lifecycleRefreshes += 1; };
            try {
              const beforeLifecyclePosts = posts.length;
              byId("failure-lifecycle-ack-button").click();
              await waitFor(
                () => posts.some((entry) => entry.path.includes("/api/failures/lifecycle") && entry.body?.transition === "acknowledge"),
                "failure lifecycle acknowledge post"
              );
              await waitFor(() => !byId("failure-lifecycle-start-button").disabled, "failure lifecycle start button ready");
              byId("failure-lifecycle-start-button").click();
              await waitFor(
                () => posts.some((entry) => entry.path.includes("/api/failures/lifecycle") && entry.body?.transition === "start_work"),
                "failure lifecycle start-work post"
              );
              await waitFor(() => !byId("failure-lifecycle-resolve-preview-button").disabled, "failure lifecycle resolve preview button ready");
              if (!byId("failure-lifecycle-resolve-confirm-button").disabled) {
                throw new Error("failure lifecycle resolve confirm should require a dry-run preview");
              }
              byId("failure-lifecycle-resolve-preview-button").click();
              await waitFor(() => text("failure-lifecycle-result").includes("Fingerprint: smoke-lifecycle-fingerprint"), "failure lifecycle resolve preview");
              await waitFor(() => !byId("failure-lifecycle-resolve-confirm-button").disabled, "failure lifecycle resolve confirm enabled after preview");
              byId("failure-lifecycle-resolve-confirm-button").click();
              await waitFor(
                () => posts.some((entry) => entry.path.includes("/api/failures/lifecycle") && entry.body?.transition === "mark_resolved" && entry.body?.confirm_transition === true),
                "failure lifecycle resolve confirm post"
              );
              byId("failure-lifecycle-resolve-confirm-button").click();
              const lifecyclePosts = posts.filter((entry) => entry.path.includes("/api/failures/lifecycle"));
              if (lifecyclePosts.length !== 4) {
                throw new Error("failure lifecycle duplicate guard expected 4 posts, saw " + lifecyclePosts.length);
              }
              if (posts.length !== beforeLifecyclePosts + 4) {
                throw new Error("failure lifecycle flow posted unexpected commands");
              }
              if (lifecycleRefreshes !== 3) {
                throw new Error("failure lifecycle non-dry-run transitions should request refresh exactly three times");
              }
            } finally {
              window.refreshAll = originalRefreshAllForLifecycle;
            }
            const moreMenu = byId("failure-more-actions");
            moreMenu.open = true;
            requireText("failure-diagnostics-actions", [
              "Read Latest Failure",
              "Open Failure JSON",
              "Open Failure Reports",
              "Open Run Logs",
              "Open Failure Markers",
            ]);
            window.mediaPipelineReportsView.renderFailurePreview({
              source: "C:/Reports/failures.json",
              source_kind: "latest_json",
              count: 1,
              operator_required_count: 0,
              permanent_count: 0,
              transient_count: 1,
              rows: [{
                source_json: "C:/Reports/failures.json",
                source_path: "C:/Source/Retry Latest.mkv",
                lookup_title: "Retry Latest",
                media_type: "movie",
                classification: "transient",
                error_code: "SUBTITLE_BDPGS_OCR_FAILED",
                stage: "subtitle-extract",
                reason: "BDPGS subtitle OCR failed.",
                suggested_action: "Configure PgsToSrt before retry.",
                retry_count: 1,
                retry_limit: 5,
                triage: {
                  status_label: "Will retry",
                  severity: "warning",
                  plain_summary: "BDPGS subtitle OCR failed.",
                  suggested_fix: "Configure PgsToSrt before retry.",
                  safe_next_action: "Backend will retry this transient failure on the next backend queue pass.",
                  detail_available: true,
                },
                clear_error: {
                  available: true,
                  marker_path: "C:/State/Failures/Markers/latest-warning-a.json",
                  marker_paths: [
                    "C:/State/Failures/Markers/latest-warning-a.json",
                    "C:/State/Failures/Markers/latest-warning-b.json",
                  ],
                  marker_count: 2,
                  unavailable_reason: "",
                },
              }],
            });
            requireText("failure-rows", [
              "Will retry",
              "Retry Latest",
              "Configure PgsToSrt before retry.",
              "Marker: available",
            ]);
            requireText("failure-resolution-summary-strip", [
              "Will retry",
              "Wait for backend retry",
              "Clearable markers",
              "2",
            ]);
            byId("failure-clear-scope").value = "selected_group";
            byId("failure-clear-preview-button").click();
            await waitFor(
              () => posts.some((entry) => entry.path.includes("/api/failures/clear") && entry.body?.dry_run === true && Array.isArray(entry.body?.marker_paths) && entry.body.marker_paths.includes("C:/State/Failures/Markers/latest-warning-b.json")),
              "latest-json retryable warning clear preview"
            );
            requireText("failure-clear-summary", [
              "Dry run: yes",
              "Planned marker clears: 2",
              "C:/State/Failures/Markers/latest-warning-a.json",
              "C:/State/Failures/Markers/latest-warning-b.json",
              "Guardrail:",
            ]);
            byId("failure-clear-confirm-button").click();
            await waitFor(
              () => posts.some((entry) => entry.path.includes("/api/failures/clear") && entry.body?.confirm_clear === true && Array.isArray(entry.body?.marker_paths) && entry.body.marker_paths.includes("C:/State/Failures/Markers/latest-warning-b.json")),
              "latest-json retryable warning clear post"
            );
            const latestWarningClearPost = posts.find((entry) => entry.path.includes("/api/failures/clear") && entry.body?.confirm_clear === true && Array.isArray(entry.body?.marker_paths) && entry.body.marker_paths.includes("C:/State/Failures/Markers/latest-warning-b.json"));
            if (latestWarningClearPost.body.scope !== "selected") throw new Error("latest-json warning clear did not use selected scope");
            if (latestWarningClearPost.body.marker_paths.length !== 2) throw new Error("latest-json warning clear did not post every marker path");
            const markerFailurePreview = {
              source: "C:/State/Failures/Markers",
              source_kind: "markers",
              count: 2,
              operator_required_count: 0,
              permanent_count: 0,
              transient_count: 2,
              rows: [{
                source_json: "C:/State/Failures/Markers/marker-1.json",
                source_path: "C:/Source/Retry One.mkv",
                lookup_title: "Retry One",
                media_type: "movie",
                classification: "transient",
                error_code: "SOURCE_LOCKED",
                stage: "scratch-copy",
                reason: "Source was locked.",
                suggested_action: "Retry after the lock clears.",
                retry_count: 1,
                retry_limit: 5,
                recorded_at: "2026-05-14T23:00:00-04:00",
                triage: {
                  status_label: "Will retry",
                  severity: "warning",
                  plain_summary: "Source was locked.",
                  suggested_fix: "Retry after the lock clears.",
                  safe_next_action: "Backend will retry this transient failure on the next backend queue pass.",
                  detail_available: true,
                },
                clear_error: {
                  available: true,
                  marker_path: "C:/State/Failures/Markers/marker-1.json",
                  unavailable_reason: "",
                },
              }, {
                source_json: "C:/State/Failures/Markers/marker-2.json",
                source_path: "C:/Source/Retry Two.mkv",
                lookup_title: "Retry Two",
                media_type: "movie",
                classification: "transient",
                error_code: "NETWORK_TEMPORARY",
                stage: "publish",
                reason: "Destination was unavailable.",
                suggested_action: "Retry after the share is online.",
                retry_count: 0,
                retry_limit: 5,
                recorded_at: "2026-05-14T23:05:00-04:00",
                triage: {
                  status_label: "Will retry",
                  severity: "warning",
                  plain_summary: "Destination was unavailable.",
                  suggested_fix: "Retry after the share is online.",
                  safe_next_action: "Backend will retry this transient failure on the next backend queue pass.",
                  detail_available: true,
                },
                clear_error: {
                  available: true,
                  marker_path: "C:/State/Failures/Markers/marker-2.json",
                  unavailable_reason: "",
                },
              }],
            };
            window.mediaPipelineReportsView.renderFailurePreview(markerFailurePreview);
            window.mediaPipelineReportsView.initReportsViewEvents();
            const hiddenFailureCheckbox = document.querySelector('#failure-rows input[type="checkbox"]');
            if (!hiddenFailureCheckbox) throw new Error("failure hidden-selection checkbox missing");
            hiddenFailureCheckbox.click();
            clickFirst('[data-failure-filter-chip="working"]', "Failure Working filter");
            requireText("failure-status", ["1 selected hidden by filter"]);
            const beforeHiddenFailurePosts = posts.length;
            byId("failure-clear-scope").value = "selected_files";
            byId("failure-clear-preview-button").click();
            byId("failure-clear-confirm-button").click();
            if (posts.length !== beforeHiddenFailurePosts) {
              throw new Error("hidden failure selected cleanup posted unexpectedly");
            }
            requireText("failure-clear-summary", ["selected failure row", "hidden by the active filter/search"]);
            clickFirst('[data-failure-filter-chip="all"]', "Failure All filter");
            const largeFailureRows = Array.from({ length: 260 }, (_, index) => ({
              ...markerFailurePreview.rows[0],
              source_json: "C:/State/Failures/Markers/marker-large-" + index + ".json",
              source_path: "C:/Source/Large Failure " + index + ".mkv",
              lookup_title: "Large Failure " + index,
              clear_error: { available: true, marker_path: "C:/State/Failures/Markers/marker-large-" + index + ".json" },
            }));
            window.mediaPipelineReportsView.renderFailurePreview({ ...markerFailurePreview, count: 260, rows: largeFailureRows });
            requireText("failure-status", ["showing first 250 of 260"]);
            window.mediaPipelineReportsView.renderFailurePreview(markerFailurePreview);
            requireText("failure-resolution-groups", [
              "Source was locked.",
              "Destination was unavailable.",
              "Wait for backend retry",
            ]);
            const firstGroup = document.querySelector('#failure-resolution-groups button[data-group-key]');
            if (!firstGroup) throw new Error("failure resolution group button missing");
            firstGroup.click();
            byId("failure-clear-scope").value = "selected_group";
            if (!byId("failure-clear-confirm-button").disabled) {
              throw new Error("marker clear confirm should stay disabled until the selected scope has a successful preview");
            }
            byId("failure-clear-preview-button").click();
            await waitFor(
              () => posts.some((entry) => entry.path.includes("/api/failures/clear") && entry.body?.dry_run === true && entry.body?.marker_paths?.[0] === "C:/State/Failures/Markers/marker-1.json"),
              "row clear preview post"
            );
            await waitFor(() => !byId("failure-clear-confirm-button").disabled, "row clear confirm enabled after preview");
            const originalRefreshAllForRowClear = window.refreshAll;
            window.refreshAll = async () => {};
            try {
              byId("failure-clear-confirm-button").click();
              await waitFor(
                () => posts.some((entry) => entry.path.includes("/api/failures/clear") && entry.body?.confirm_clear === true && entry.body?.marker_paths?.[0] === "C:/State/Failures/Markers/marker-1.json"),
                "row clear post"
              );
            } finally {
              window.refreshAll = originalRefreshAllForRowClear;
            }
            const rowClearPost = posts.find((entry) => entry.path.includes("/api/failures/clear") && entry.body?.confirm_clear === true && entry.body?.marker_paths?.[0] === "C:/State/Failures/Markers/marker-1.json");
            if (rowClearPost.body.scope !== "selected") throw new Error("row clear did not use selected scope");
            if (rowClearPost.body.dry_run !== false) throw new Error("row clear must not be a dry run");
            if (!Array.isArray(rowClearPost.body.marker_paths) || rowClearPost.body.marker_paths.length !== 1) {
              throw new Error("row clear did not send exactly one marker path");
            }
            if (rowClearPost.body.marker_paths[0] !== "C:/State/Failures/Markers/marker-1.json") {
              throw new Error("row clear posted the wrong marker path");
            }
            window.mediaPipelineReportsView.renderFailurePreview(markerFailurePreview);
            const originalRefreshAllForClear = window.refreshAll;
            let bulkRefreshStarted = false;
            let releaseBulkRefresh = () => {};
            window.refreshAll = () => new Promise((resolve) => {
              bulkRefreshStarted = true;
              releaseBulkRefresh = resolve;
            });
            try {
              if (!byId("failure-clear-confirm-button").disabled) {
                throw new Error("clear-all confirm should be disabled until the all active markers preview completes");
              }
              const beforeBulkClearPosts = posts.length;
              byId("failure-clear-scope").value = "all_markers";
              byId("failure-clear-preview-button").click();
              await waitFor(() => text("failure-clear-status").includes("Preview ready"), "failure marker clear all preview");
              await waitFor(() => !byId("failure-clear-confirm-button").disabled, "failure clear confirm enabled after all active markers preview");
              byId("failure-clear-confirm-button").click();
              await waitFor(() => text("failure-clear-status").includes("Cleared"), "failure marker clear all success");
              const bulkClearPost = posts.find((entry) => entry.path.includes("/api/failures/clear") && entry.body?.scope === "all_markers" && entry.body?.dry_run === false);
              if (!bulkClearPost) throw new Error("Clear all active markers did not post after preview.");
              if (bulkClearPost.body.confirm_clear !== true) throw new Error("Clear all active markers must send confirm_clear true.");
              if (Object.prototype.hasOwnProperty.call(bulkClearPost.body, "marker_paths")) {
                throw new Error("Clear all active markers must let the backend enumerate marker paths.");
              }
              byId("failure-clear-confirm-button").click();
              if (posts.length !== beforeBulkClearPosts + 2) {
                throw new Error("Clear all active markers duplicate click posted more than once.");
              }
              if (!bulkRefreshStarted) throw new Error("clear-all did not request the authoritative refresh");
              requireText("failure-summary", [
                "Source type: markers",
                "Rows: 0",
                "No failure rows found for the selected source",
              ]);
              requireText("failure-rows", ["No failure rows found for the selected source"]);
              if (text("failure-rows").includes("Retry One") || text("failure-rows").includes("Retry Two")) {
                throw new Error("clear-all left stale marker rows visible before refresh completed");
              }
              if (text("failure-status") !== "0 / 0 rows") {
                throw new Error("clear-all did not update the visible failure row count immediately: " + text("failure-status"));
              }
            } finally {
              releaseBulkRefresh();
              window.refreshAll = originalRefreshAllForClear;
            }
            window.mediaPipelineReportsView.renderFailurePreview(markerFailurePreview);
            const originalRefreshAllForArchive = window.refreshAll;
            let archiveRefreshStarted = false;
            let releaseArchiveRefresh = () => {};
            window.refreshAll = () => new Promise((resolve) => {
              archiveRefreshStarted = true;
              releaseArchiveRefresh = resolve;
            });
            try {
              byId("failure-archive-disclosure").open = true;
              if (!byId("failure-archive-confirm-button").disabled) {
                throw new Error("archive evidence confirm should stay disabled until preview and reason are present");
              }
              byId("failure-archive-preview-button").click();
              await waitFor(() => text("failure-archive-status").includes("Preview ready"), "failure archive preview ready");
              requireText("failure-archive-summary", [
                "Dry run: yes",
                "Planned evidence files: 3",
                "Fingerprint: smoke-archive-fingerprint",
                "Guardrail:",
              ]);
              if (!byId("failure-archive-confirm-button").disabled) {
                throw new Error("archive evidence confirm should stay disabled until a reason is entered");
              }
              byId("failure-archive-reason").value = "Smoke test evidence cleanup";
              byId("failure-archive-reason").dispatchEvent(new Event("input", { bubbles: true }));
              await waitFor(() => !byId("failure-archive-confirm-button").disabled, "failure archive confirm enabled after preview and reason");
              byId("failure-archive-confirm-button").click();
              await waitFor(() => text("failure-archive-status").includes("Archived"), "failure archive confirmed");
              const archiveConfirmPost = posts.find((entry) => entry.path.includes("/api/failures/archive-evidence") && entry.body?.confirm_archive === true);
              if (!archiveConfirmPost) throw new Error("archive evidence confirm did not post");
              if (archiveConfirmPost.body.scope !== "all_active") throw new Error("archive evidence did not use all_active scope");
              if (archiveConfirmPost.body.reason !== "Smoke test evidence cleanup") throw new Error("archive evidence did not send the operator reason");
              if (archiveConfirmPost.body.dry_run_fingerprint !== "smoke-archive-fingerprint") throw new Error("archive evidence did not send dry-run fingerprint");
              if (!archiveRefreshStarted) throw new Error("archive evidence did not request the authoritative refresh");
            } finally {
              releaseArchiveRefresh();
              window.refreshAll = originalRefreshAllForArchive;
            }
            window.mediaPipelineReportsView.renderReports(
              {
                latest_paths: {
                  latest_failure_report: "C:/Reports/failures.txt",
                  latest_failure_json: "C:/Reports/failures.json",
                  latest_audit_csv: "C:/Reports/audit_summary.csv",
                  latest_priority_csv: "C:/Reports/audit_priority.csv",
                },
                warnings: [],
                audit_progress: {
                  status: "completed",
                  completed: true,
                  processed_files: 10,
                  total_files: 10,
                  percent_complete: 100,
                  current_operation: "Audit report fixture idle.",
                },
                progress_bars: [{
                  id: "audit_progress",
                  label: "Audit progress",
                  mode: "determinate",
                  percent: 100,
                  status: "complete",
                  detail: "10 / 10 | completed",
                  source: "audit_progress.json",
                  updated_at: "2026-05-17T12:05:00Z",
                }],
              },
              {
                paths: {
                  failed_reports: "C:/Reports/Failures",
                  failed_markers: "C:/State/FailedMarkers",
                  audit_reports: "C:/Reports/Audit",
                  completed_manifest: "C:/State/Completed/completed_jobs.jsonl",
                  pending_push: "C:/PendingServerPush",
                  queue_snapshot: "C:/State/Progress/queue_snapshot.json",
                  active_jobs: "C:/State/ActiveJobs",
                },
              }
            );
            window.mediaPipelineReportsView.renderFailurePreview(reportFailurePreview);
            window.mediaPipelineReportsView.renderAuditPreview(reportAuditPreview);
            window.mediaPipelineReportsView.renderAuditControls(reportAuditControls);
            clickFirst('[data-reports-tab="audit"]', "Reports Audit tab");
            await waitFor(() => document.querySelector('[data-reports-tab="audit"]')?.getAttribute("aria-selected") === "true", "Reports Audit tab selected");
            const largeAuditRows = Array.from({ length: 260 }, (_, index) => ({
              ...reportAuditPreview.rows[0],
              path: "C:/Outsource/Large Audit " + index + ".mkv",
              relative_path: "Large Audit " + index + ".mkv",
              lookup_title: "Large Audit " + index,
              priority_score: 95 - (index % 10),
            }));
            window.mediaPipelineReportsView.renderAuditPreview({ ...reportAuditPreview, count: 260, rows: largeAuditRows });
            requireText("audit-preview-status", ["showing first 250 of 260"]);
            window.mediaPipelineReportsView.renderAuditPreview(reportAuditPreview);
            requireText("report-audit-score-policy-summary", [
              "Score policy source: defaults",
              "Audit ignore entries: 0",
              "Advanced score controls: enable Advanced mode",
              "Boundary: score and ignore controls affect audit reporting/export only",
            ]);
            const scoreDisclosure = document.querySelector('#report-audit-score-redownload-bucket')?.closest('details');
            if (!scoreDisclosure || !scoreDisclosure.hasAttribute("data-advanced")) {
              throw new Error("Reports audit score controls are not behind the Advanced gate.");
            }
            if (window.getComputedStyle(scoreDisclosure).display !== "none") {
              throw new Error("Reports audit score controls should be hidden before Advanced mode is enabled.");
            }
            if (!scoreDisclosure.textContent.includes("High issue-code marker") || !scoreDisclosure.textContent.includes("audio-default-policy-mismatch")) {
              throw new Error("Reports audit score controls did not list high issue-code markers.");
            }
            if (!scoreDisclosure.textContent.includes("Medium issue-code marker") || !scoreDisclosure.textContent.includes("bdpgs-subtitles-ocr-candidate")) {
              throw new Error("Reports audit score controls did not list medium issue-code markers.");
            }
            if (!scoreDisclosure.textContent.includes("High issue: ffprobe-open-failed") || !scoreDisclosure.textContent.includes("High issue: foreign-audio-no-text-subtitles")) {
              throw new Error("Reports audit score controls did not list every high issue-code marker as a point issue.");
            }
            if (!scoreDisclosure.textContent.includes("Medium issue: multiple-video-streams") || !scoreDisclosure.textContent.includes("Medium issue: ambiguous-tv-naming")) {
              throw new Error("Reports audit score controls did not list every medium issue-code marker as a point issue.");
            }
            if (scoreDisclosure.querySelector("[data-audit-score-policy-mirror]")) {
              throw new Error("Reports audit score controls still rendered locked mirror rows.");
            }
            const highScoreInput = scoreDisclosure.querySelector('[data-audit-score-issue-code="audio-default-policy-mismatch"]');
            const persistedHighScoreInput = scoreDisclosure.querySelector('[data-audit-score-issue-code="ffprobe-open-failed"]');
            const mediumScoreInput = scoreDisclosure.querySelector('[data-audit-score-issue-code="bdpgs-subtitles-ocr-candidate"]');
            if (!highScoreInput || highScoreInput.tagName !== "INPUT" || highScoreInput.type !== "number" || highScoreInput.value !== "90") {
              throw new Error("Reports high issue marker row was not an editable numeric input.");
            }
            if (!persistedHighScoreInput || persistedHighScoreInput.value !== "95") {
              throw new Error("Reports high issue-code input did not reflect the saved per-code policy.");
            }
            if (!mediumScoreInput || mediumScoreInput.tagName !== "INPUT" || mediumScoreInput.type !== "number" || mediumScoreInput.value !== "40") {
              throw new Error("Reports medium issue marker row was not an editable numeric input.");
            }
            const highDefaultInput = byId("report-audit-score-high-issue");
            highDefaultInput.value = "111";
            highDefaultInput.dispatchEvent(new Event("input", { bubbles: true }));
            if (highScoreInput.value !== "111") {
              throw new Error("Reports high group default did not update untouched high issue-code rows.");
            }
            if (persistedHighScoreInput.value !== "95") {
              throw new Error("Reports high group default overwrote a saved per-code override.");
            }
            highScoreInput.value = "222";
            highScoreInput.dispatchEvent(new Event("input", { bubbles: true }));
            highDefaultInput.value = "333";
            highDefaultInput.dispatchEvent(new Event("input", { bubbles: true }));
            if (highScoreInput.value !== "222") {
              throw new Error("Reports manually edited high issue-code row did not stay independent.");
            }
            [
              "report-audit-start-button",
              "report-audit-stop-button",
              "report-audit-start-library-root",
              "report-audit-saved-location-select",
              "report-audit-save-location-button",
              "report-audit-remove-location-button",
              "report-audit-location-summary",
              "report-audit-start-include-sidecars",
              "report-audit-start-show-console",
              "report-audit-score-policy-save-button",
              "report-audit-score-policy-reset-button",
              "report-audit-ignore-selected-button",
              "report-audit-export-rerun-csv-button",
            ].forEach((id) => {
              if (!byId(id)) throw new Error("missing Reports audit control " + id);
            });
            if (!document.querySelector('[data-audit-selection-action="select-visible"]')) {
              throw new Error("missing Reports audit Select All control");
            }
            if (!document.querySelector('[data-audit-score-threshold-input]')) {
              throw new Error("missing Reports audit minimum score control");
            }
            if (!document.querySelector('[data-audit-selection-action="select-score-at-least"]')) {
              throw new Error("missing Reports audit score threshold selection control");
            }
            if (!document.querySelector('[data-audit-selection-action="clear"]')) {
              throw new Error("missing Reports audit clear selection control");
            }
            try { localStorage.removeItem("mediapipeline-report-audit-locations.v1"); } catch (_) {}
            const dispatchAuditLocationInput = () => byId("report-audit-start-library-root").dispatchEvent(new Event("input", { bubbles: true }));
            byId("report-audit-start-library-root").value = "C:/Reports/Library";
            dispatchAuditLocationInput();
            byId("report-audit-save-location-button").click();
            requireText("report-audit-location-summary", [
              "Saved audit locations: 1/10",
              "C:/Reports/Library",
              "Start Audit submits one staged library root",
            ]);
            for (let index = 2; index <= 10; index += 1) {
              byId("report-audit-start-library-root").value = "C:/Reports/Library " + index;
              dispatchAuditLocationInput();
              byId("report-audit-save-location-button").click();
            }
            requireText("report-audit-location-summary", ["Saved audit locations: 10/10"]);
            byId("report-audit-start-library-root").value = "C:/Reports/Library 11";
            dispatchAuditLocationInput();
            if (!byId("report-audit-save-location-button").disabled) {
              throw new Error("Reports audit saved-location control allowed more than 10 saved roots.");
            }
            requireText("report-audit-location-summary", ["Saved location limit reached"]);
            byId("report-audit-saved-location-select").value = "C:/Reports/Library";
            byId("report-audit-saved-location-select").dispatchEvent(new Event("change", { bubbles: true }));
            if (byId("report-audit-start-library-root").value !== "C:/Reports/Library") {
              throw new Error("Reports audit saved-location select did not stage the selected root.");
            }
            byId("report-audit-remove-location-button").click();
            requireText("report-audit-location-summary", [
              "Saved audit locations: 9/10",
              "Removed saved audit location.",
            ]);
            if (posts.some((entry) => entry.path.includes("/api/audit/start"))) {
              throw new Error("Reports posted audit start before the explicit Start Audit click.");
            }
            const originalConfirm = window.confirm;
            byId("report-audit-start-library-root").value = "C:/Reports/Library";
            byId("report-audit-start-include-sidecars").checked = true;
            byId("report-audit-start-show-console").checked = false;
            window.confirm = () => true;
            const beforeAuditStartPosts = posts.filter((entry) => entry.path.includes("/api/audit/start")).length;
            byId("report-audit-start-button").click();
            byId("report-audit-start-button").click();
            await waitFor(() => posts.some((entry) => entry.path.includes("/api/audit/start")), "reports audit start");
            if (posts.filter((entry) => entry.path.includes("/api/audit/start")).length !== beforeAuditStartPosts + 1) {
              throw new Error("Reports audit start duplicate click posted more than once.");
            }
            const auditStartPost = posts.find((entry) => entry.path.includes("/api/audit/start"));
            if (auditStartPost.body?.library_root !== "C:/Reports/Library") {
              throw new Error("Reports audit start did not submit the staged library root.");
            }
            if (auditStartPost.body?.include_sidecars !== true) {
              throw new Error("Reports audit start did not submit include_sidecars.");
            }
            await waitFor(() => text("report-audit-launch-status").includes("Running"), "reports audit running indicator");
            if (!byId("report-audit-start-button").disabled) {
              throw new Error("Reports audit start button became clickable while the accepted audit run was still active.");
            }
            if (text("report-audit-start-button") !== "Audit Running") {
              throw new Error("Reports audit start button did not switch to Audit Running.");
            }
            if (byId("report-audit-stop-button").disabled) {
              throw new Error("Reports audit stop button was not clickable while the accepted audit run was active.");
            }
            requireText("report-audit-launch-detail", [
              "Running indicator:",
              "Elapsed:",
              "ETA: unavailable",
              "Progress source:",
            ]);
            requireText("report-progress-summary", [
              "Audit status: starting",
              "Backend accepted audit start",
            ]);
            const beforeAuditStopPosts = posts.filter((entry) => entry.path.includes("/api/audit/stop")).length;
            byId("report-audit-stop-button").click();
            byId("report-audit-stop-button").click();
            await waitFor(() => posts.some((entry) => entry.path.includes("/api/audit/stop")), "reports audit stop");
            if (posts.filter((entry) => entry.path.includes("/api/audit/stop")).length !== beforeAuditStopPosts + 1) {
              throw new Error("Reports audit stop duplicate click posted more than once.");
            }
            const auditStopPost = posts.find((entry) => entry.path.includes("/api/audit/stop"));
            if (auditStopPost.body?.confirm_stop !== true) {
              throw new Error("Reports audit stop did not submit confirm_stop true.");
            }
            requireText("report-audit-launch-detail", [
              "audit.stop",
              "Audit stop recorded",
              "confirm_stop",
            ]);
            window.confirm = () => true;
            const beforeScorePolicyPosts = posts.filter((entry) => entry.path.includes("/api/audit/score-policy")).length;
            byId("report-audit-score-policy-save-button").click();
            byId("report-audit-score-policy-save-button").click();
            await waitFor(() => posts.some((entry) => entry.path.includes("/api/audit/score-policy")), "audit score policy save");
            if (posts.filter((entry) => entry.path.includes("/api/audit/score-policy")).length !== beforeScorePolicyPosts + 1) {
              throw new Error("Reports audit score policy duplicate click posted more than once.");
            }
            window.confirm = originalConfirm;
            const scorePolicyPost = posts.find((entry) => entry.path.includes("/api/audit/score-policy"));
            if (scorePolicyPost.body?.policy?.issue_code_weights?.["audio-default-policy-mismatch"] !== 222) {
              throw new Error("Reports audit score policy save did not include edited issue_code_weights.");
            }
            if (scorePolicyPost.body?.policy?.issue_code_weights?.["bdpgs-subtitles-ocr-candidate"] !== 40) {
              throw new Error("Reports audit score policy save did not include medium issue_code_weights.");
            }
            await waitFor(() => !byId("report-audit-export-rerun-csv-button").disabled, "audit command buttons re-enabled after score policy save");
            window.mediaPipelineReportsView.renderFailurePreview(reportFailurePreview);
            window.mediaPipelineReportsView.renderAuditPreview(reportAuditPreview);
            window.mediaPipelineReportsView.renderAuditControls(reportAuditControls);
            const auditSelectAllButton = document.querySelector('[data-audit-selection-action="select-visible"]');
            if (auditSelectAllButton.disabled) {
              throw new Error("Reports audit Select All control was disabled with visible audit rows.");
            }
            if (typeof auditSelectAllButton.onclick !== "function") {
              throw new Error("Reports audit Select All control was not bound.");
            }
            clickFirst('[data-audit-selection-action="select-visible"]', "Audit Select All");
            if (!text("audit-preview-status").includes("1 selected")) {
              throw new Error("Reports audit Select All did not select visible rows: " + JSON.stringify({
                status: text("audit-preview-status"),
                action: auditSelectAllButton.dataset.auditSelectionAction,
                disabled: auditSelectAllButton.disabled,
                keys: window.mediaPipelineReportsView.selectedAuditRowKeysList(),
                visibleRows: document.querySelectorAll('#audit-preview-rows tr[data-row-key]').length,
              }));
            }
            requireText("report-audit-export-detail", [
              "Select All",
              "selected 1 audit row",
              "current filter/search",
            ]);
            clickFirst('[data-audit-selection-action="clear"]', "Audit Clear Selection");
            requireText("report-audit-export-status", ["No selection"]);
            const scoreThresholdInput = document.querySelector('[data-audit-score-threshold-input]');
            scoreThresholdInput.value = "90";
            clickFirst('[data-audit-selection-action="select-score-at-least"]', "Audit Select Score or Higher");
            requireText("audit-preview-status", ["1 selected"]);
            requireText("report-audit-export-detail", [
              "Select Score or Higher (90)",
              "selected 1 audit row",
            ]);
            clickFirst('[data-audit-selection-action="clear"]', "Audit Clear Selection After Score");
            const auditCheckbox = document.querySelector('#audit-preview-rows input[type="checkbox"]');
            if (!auditCheckbox) throw new Error("Reports audit row multi-select checkbox missing");
            auditCheckbox.click();
            if (!document.querySelector('#audit-preview-rows input[type="checkbox"]')?.checked) {
              throw new Error("Reports audit row multi-select checkbox did not stay checked");
            }
            requireText("audit-preview-status", ["1 selected"]);
            requireText("report-audit-export-status", ["1 selected"]);
            requireText("audit-preview-rows", [
              "RERUN_PIPELINE",
              "subtitle_missing_srt",
              "Launch CSV Rerun",
            ]);
            clickFirst('[data-audit-filter-chip="redownload"]', "Audit Redownload filter");
            requireText("audit-preview-status", ["1 selected hidden by filter"]);
            const beforeHiddenAuditPosts = posts.length;
            byId("report-audit-ignore-selected-button").click();
            byId("report-audit-export-rerun-csv-button").click();
            if (posts.length !== beforeHiddenAuditPosts) {
              throw new Error("hidden audit selected action posted unexpectedly");
            }
            requireText("report-audit-export-detail", ["selected audit row", "hidden by the active filter/search"]);
            clickFirst('[data-audit-filter-chip="all"]', "Audit All filter");
            clickFirst('#audit-preview-rows tr[data-row-key]', "audit row");
            requireText("audit-preview-detail", [
              "Reports audit selected row",
              "Bucket: RERUN_PIPELINE",
              "Issue: subtitle_missing_srt",
              "Suggested action: Rerun pipeline for preferred-language SRT.",
              "Owner routing",
              "Evidence owner: Diagnostics",
              "Action owner: Launch CSV Rerun",
            ]);
            requireText("audit-preview-diagnostics-actions", ["Go to Launch"]);
            clickFirst('[data-reports-tab="files"]', "Reports Locations tab");
            requireText("report-triage", [
              "Failure rows: 1",
              "Audit rows: 1",
              "Mutation guardrail:",
            ]);
            if (byId("report-launch-handoff") || byId("report-go-rerun-button") || document.querySelector('[data-reports-tab="overview"]')) {
              throw new Error("Reports pre-launch/overview surface was still present after tab navigation.");
            }

            const forbidden = [
              "/api/pipeline/start",
              "/api/rerun/start",
              "/api/maintenance/release-dry-run",
              "/api/maintenance/release-build",
              "/api/maintenance/completed-backfill-dry-run",
              "/api/maintenance/dependency-atlas",
              "/api/maintenance/dependency-atlas/open-folder",
              "/api/settings/save-patch",
              "/api/rename/apply",
              "/api/pending-publish/drain",
            ];
            const forbiddenPosts = posts.filter((entry) => {
              return forbidden.some((path) => entry.path.includes(path));
            });
            if (forbiddenPosts.length) throw new Error("maintenance/reports smoke posted mutation routes: " + JSON.stringify(forbiddenPosts));
            window.apiGet = originalApiGet;
            window.apiPost = originalApiPost;
            return {
              ok: true,
              posts,
              gets,
              maintenanceStatus: text("maintenance-readiness-status"),
              reportStatus: text("report-triage-status"),
              failureStatus: text("failure-review-status"),
              auditStatus: text("audit-review-status"),
            };
          })()
          `;
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`,
            payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.getElementById("maintenance-readiness") && document.getElementById("report-triage") && (typeof window.showPage === "function" || typeof window.mediaPipelineAppLifecycle?.showPage === "function") && typeof window.mediaPipelineMaintenanceView.renderMaintenance === "function" && typeof window.mediaPipelineReportsView.renderReports === "function" && typeof window.mediaPipelineReportsView.renderFailurePreview === "function" && typeof window.mediaPipelineReportsView.renderAuditPreview === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("maintenance-readiness") && document.getElementById("report-triage") && (typeof window.showPage === "function" || typeof window.mediaPipelineAppLifecycle?.showPage === "function") && typeof window.mediaPipelineMaintenanceView.renderMaintenance === "function" && typeof window.mediaPipelineReportsView.renderReports === "function" && typeof window.mediaPipelineReportsView.renderFailurePreview === "function" && typeof window.mediaPipelineReportsView.renderAuditPreview === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Maintenance/Reports WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: maintenanceReportsScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await sleep(750);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_maintenance_reports_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView maintenance/reports smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-maintenance-reports-payload.json"
        runner_path = tmp / "browser-maintenance-reports-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_maintenance_reports_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Maintenance/Reports smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserMaintenanceReportsSmoke(unittest.TestCase):
    def test_real_browser_renders_maintenance_reports_and_clear_error_payloads(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView maintenance/reports smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-maintenance-reports-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_maintenance_reports_smoke(browser_path=browser_path, url=f"{server.url}/")
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        posts = browser_result["posts"]
        gets = browser_result["gets"]
        self.assertEqual(len(posts), 16)
        failure_get_paths = [get["path"] for get in gets if get["path"].startswith("/api/failures")]
        self.assertIn("/api/failures?limit=100&source=markers", failure_get_paths)
        self.assertIn("/api/failures?limit=100", failure_get_paths)
        audit_start_post = next(post for post in posts if post["path"] == "/api/audit/start")
        audit_stop_post = next(post for post in posts if post["path"] == "/api/audit/stop")
        score_policy_post = next(post for post in posts if post["path"] == "/api/audit/score-policy")
        diagnostics_open_post = next(post for post in posts if post["path"] == "/api/diagnostics/open")
        lifecycle_posts = [post for post in posts if post["path"] == "/api/failures/lifecycle"]
        lifecycle_ack = next(post for post in lifecycle_posts if post["body"].get("transition") == "acknowledge")
        lifecycle_start = next(post for post in lifecycle_posts if post["body"].get("transition") == "start_work")
        lifecycle_resolve_preview = next(
            post
            for post in lifecycle_posts
            if post["body"].get("transition") == "mark_resolved" and post["body"].get("dry_run") is True
        )
        lifecycle_resolve_confirm = next(
            post
            for post in lifecycle_posts
            if post["body"].get("transition") == "mark_resolved" and post["body"].get("confirm_transition") is True
        )
        latest_warning_preview = next(
            post
            for post in posts
            if post["path"] == "/api/failures/clear"
            and post["body"].get("dry_run") is True
            and "C:/State/Failures/Markers/latest-warning-b.json" in post["body"].get("marker_paths", [])
        )
        latest_warning_clear = next(
            post
            for post in posts
            if post["path"] == "/api/failures/clear"
            and post["body"].get("confirm_clear") is True
            and "C:/State/Failures/Markers/latest-warning-b.json" in post["body"].get("marker_paths", [])
        )
        row_preview = next(
            post
            for post in posts
            if post["path"] == "/api/failures/clear"
            and post["body"].get("dry_run") is True
            and post["body"].get("marker_paths") == ["C:/State/Failures/Markers/marker-1.json"]
        )
        row_clear = next(
            post
            for post in posts
            if post["path"] == "/api/failures/clear"
            and post["body"].get("confirm_clear") is True
            and post["body"].get("marker_paths") == ["C:/State/Failures/Markers/marker-1.json"]
        )
        bulk_preview = next(post for post in posts if post["body"].get("scope") == "all_markers" and post["body"].get("dry_run") is True)
        bulk_clear = next(post for post in posts if post["body"].get("scope") == "all_markers" and post["body"].get("dry_run") is False)
        archive_previews = [
            post
            for post in posts
            if post["path"] == "/api/failures/archive-evidence" and post["body"].get("dry_run") is True
        ]
        archive_confirm = next(
            post
            for post in posts
            if post["path"] == "/api/failures/archive-evidence" and post["body"].get("confirm_archive") is True
        )
        self.assertEqual(audit_start_post["body"]["library_root"], "C:/Reports/Library")
        self.assertTrue(audit_start_post["body"]["include_sidecars"])
        self.assertFalse(audit_start_post["body"]["show_console"])
        self.assertTrue(audit_stop_post["body"]["confirm_stop"])
        self.assertEqual(audit_stop_post["body"]["reason"], "Reports Stop Audit button")
        self.assertEqual(diagnostics_open_post["body"]["target"], "latest_failure_report")
        self.assertEqual(len(lifecycle_posts), 4)
        self.assertEqual(lifecycle_ack["body"]["journal_key"], "source_locked|source-stability|manual-review|review-in-diagnostics")
        self.assertFalse(lifecycle_ack["body"]["dry_run"])
        self.assertTrue(lifecycle_ack["body"]["confirm_transition"])
        self.assertEqual(lifecycle_start["body"]["journal_key"], lifecycle_ack["body"]["journal_key"])
        self.assertFalse(lifecycle_start["body"]["dry_run"])
        self.assertTrue(lifecycle_start["body"]["confirm_transition"])
        self.assertEqual(lifecycle_resolve_preview["body"]["reason"], "Operator marked failure resolved from Reports.")
        self.assertEqual(lifecycle_resolve_preview["body"]["operator_note"], "")
        self.assertTrue(lifecycle_resolve_preview["body"]["dry_run"])
        self.assertFalse(lifecycle_resolve_preview["body"]["confirm_transition"])
        self.assertEqual(lifecycle_resolve_preview["body"]["dry_run_fingerprint"], "")
        self.assertEqual(lifecycle_resolve_confirm["body"]["dry_run_fingerprint"], "smoke-lifecycle-fingerprint")
        self.assertFalse(lifecycle_resolve_confirm["body"]["dry_run"])
        self.assertTrue(lifecycle_resolve_confirm["body"]["confirm_transition"])
        self.assertEqual(latest_warning_preview["body"]["scope"], "selected")
        self.assertTrue(latest_warning_preview["body"]["dry_run"])
        self.assertFalse(latest_warning_preview["body"]["confirm_clear"])
        self.assertEqual(latest_warning_clear["path"], "/api/failures/clear")
        self.assertEqual(latest_warning_clear["body"]["scope"], "selected")
        self.assertFalse(latest_warning_clear["body"]["dry_run"])
        self.assertTrue(latest_warning_clear["body"]["confirm_clear"])
        self.assertEqual(
            latest_warning_clear["body"]["marker_paths"],
            [
                "C:/State/Failures/Markers/latest-warning-a.json",
                "C:/State/Failures/Markers/latest-warning-b.json",
            ],
        )
        self.assertEqual(row_preview["body"]["scope"], "selected")
        self.assertTrue(row_preview["body"]["dry_run"])
        self.assertFalse(row_preview["body"]["confirm_clear"])
        self.assertEqual(row_clear["path"], "/api/failures/clear")
        self.assertEqual(row_clear["body"]["scope"], "selected")
        self.assertFalse(row_clear["body"]["dry_run"])
        self.assertTrue(row_clear["body"]["confirm_clear"])
        self.assertEqual(row_clear["body"]["marker_paths"], ["C:/State/Failures/Markers/marker-1.json"])
        self.assertEqual(bulk_preview["path"], "/api/failures/clear")
        self.assertTrue(bulk_preview["body"]["dry_run"])
        self.assertFalse(bulk_preview["body"]["confirm_clear"])
        self.assertNotIn("marker_paths", bulk_preview["body"])
        self.assertEqual(bulk_clear["path"], "/api/failures/clear")
        self.assertEqual(bulk_clear["body"]["scope"], "all_markers")
        self.assertFalse(bulk_clear["body"]["dry_run"])
        self.assertTrue(bulk_clear["body"]["confirm_clear"])
        self.assertNotIn("marker_paths", bulk_clear["body"])
        self.assertEqual(len(archive_previews), 1)
        for archive_preview in archive_previews:
            self.assertEqual(archive_preview["body"]["scope"], "all_active")
            self.assertTrue(archive_preview["body"]["include_markers"])
            self.assertTrue(archive_preview["body"]["include_reports"])
            self.assertTrue(archive_preview["body"]["dry_run"])
            self.assertFalse(archive_preview["body"]["confirm_archive"])
            self.assertEqual(archive_preview["body"].get("dry_run_fingerprint", ""), "")
        self.assertEqual(archive_confirm["body"]["scope"], "all_active")
        self.assertTrue(archive_confirm["body"]["include_markers"])
        self.assertTrue(archive_confirm["body"]["include_reports"])
        self.assertFalse(archive_confirm["body"]["dry_run"])
        self.assertTrue(archive_confirm["body"]["confirm_archive"])
        self.assertEqual(archive_confirm["body"]["dry_run_fingerprint"], "smoke-archive-fingerprint")
        self.assertEqual(archive_confirm["body"]["reason"], "Smoke test evidence cleanup")
        self.assertEqual(score_policy_post["body"]["policy"]["issue_code_weights"]["audio-default-policy-mismatch"], 222)
        self.assertEqual(score_policy_post["body"]["policy"]["issue_code_weights"]["bdpgs-subtitles-ocr-candidate"], 40)
        self.assertIn(browser_result["maintenanceStatus"], {"Ready", "Warnings", "Blocked"})
        self.assertEqual(browser_result["reportStatus"], "Action needed")
        self.assertEqual(browser_result["failureStatus"], "Action needed")
        self.assertEqual(browser_result["auditStatus"], "Rerun review")


if __name__ == "__main__":
    unittest.main()
