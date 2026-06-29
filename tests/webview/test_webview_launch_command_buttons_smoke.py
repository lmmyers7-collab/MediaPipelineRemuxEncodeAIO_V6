from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


ROOT = find_repo_root(Path(__file__))
COMMAND_BUTTONS_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "commandButtons.js"
CONTROLLER_STATE_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "controllerState.js"
LAUNCH_READINESS_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launchReadinessView.js"
LAUNCH_VIEW_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launchView.js"
LAUNCH_SCOPE_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launchView.scope.js"
PAGE_LAUNCH_HTML = ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-launch.html"
PAGE_DIAGNOSTICS_HTML = ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-diagnostics.html"
PREFLIGHT_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launchView.preflight.js"
START_REQUEST_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "startRequest.js"


def _run_launch_command_buttons_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch command buttons smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(COMMAND_BUTTONS_JS)!r}, "utf8");
        const context = {{
          window: {{}},
          document: {{ querySelectorAll() {{ return []; }} }},
        }};
        context.window.window = context.window;
        context.window.document = context.document;
        vm.createContext(context);
        vm.runInContext(source, context);

        const factory = context.window.__launchCommandButtonsModule.createLaunchCommandButtonsModule;
        const decisionRequests = [];
        const payloads = [
          {{
            target: "pipeline",
            status: "ready",
            request: {{ mode: "continuous", sleep_seconds: 30, schedule_override: "", single_file: "" }},
            checks: [{{ key: "pipeline-ready", label: "Pipeline ready", status: "ready", action: "No action." }}],
          }},
          {{
            target: "rerun",
            _frontend_preflight_key: "rerun-live",
            _frontend_target_label: "CSV Rerun Start",
            status: "ready",
            request: {{ csv_path: "C:/rerun.csv", dry_run: false, plan_only: false, stage_mode: "copy", original_mode: "keep", return_mode: "queue" }},
            checks: [{{ key: "rerun-live-ready", label: "CSV live ready", status: "ready", action: "No action." }}],
          }},
          {{
            target: "rerun",
            _frontend_preflight_key: "rerun-preview",
            _frontend_target_label: "CSV Rerun Preview",
            status: "ready",
            request: {{ csv_path: "C:/rerun.csv", dry_run: true, plan_only: false, stage_mode: "copy", original_mode: "keep", return_mode: "queue" }},
            checks: [{{ key: "rerun-preview-ready", label: "CSV preview ready", status: "ready", action: "No action." }}],
          }},
          {{
            target: "rerun",
            _frontend_preflight_key: "rerun-plan-only",
            _frontend_target_label: "CSV Rerun Plan Only",
            status: "ready",
            request: {{ csv_path: "C:/rerun.csv", dry_run: false, plan_only: true, stage_mode: "copy", original_mode: "keep", return_mode: "queue" }},
            checks: [{{ key: "rerun-plan-only-ready", label: "CSV plan-only ready", status: "ready", action: "No action." }}],
          }},
        ];
        function valuesMatch(left, right) {{
          return JSON.stringify(left) === JSON.stringify(right);
        }}
        const rerunRequests = [];
        const launchModule = factory({{
          collectPipelineStartRequest() {{
            return {{ mode: "continuous", sleep_seconds: 30, schedule_override: "", single_file: "", pipeline_only_blocker: true }};
          }},
          collectRerunStartRequest(options = {{}}) {{
            const request = {{ csv_path: "C:/rerun.csv", dry_run: Boolean(options.dry_run), plan_only: Boolean(options.plan_only), stage_mode: "copy", original_mode: "keep", return_mode: "queue" }};
            rerunRequests.push(request);
            return request;
          }},
          launchBackendPreflightPayloadForTarget(target, options = {{}}) {{
            const candidates = payloads.filter((payload) => String(payload.target || "").toLowerCase() === String(target || "").toLowerCase());
            if (options.request && Array.isArray(options.matchKeys)) {{
              return candidates.find((payload) => options.matchKeys.every((key) => valuesMatch(payload.request?.[key], options.request?.[key]))) || null;
            }}
            return candidates[0] || null;
          }},
          launchBackendPreflightOverallStatus(items) {{
            return items.some((item) => String(item.status || "").toLowerCase() === "blocked") ? "Blocked" : "Ready";
          }},
          launchBackendPreflightRows(items) {{
            return items.flatMap((payload) => (payload.checks || []).map((check) => ({{
              check: check.label,
              posture: check.status,
              action: check.action,
            }})));
          }},
          launchPreflightRequestMatches(payload, request, keys) {{
            return keys.every((key) => valuesMatch(payload.request?.[key], request?.[key]));
          }},
          launchStartDecisionRows(request) {{
            decisionRequests.push(request);
            return [{{ posture: "blocked", signal: "Injected pipeline-only blocker" }}];
          }},
          launchStartDecisionStatus(rows) {{
            return rows.some((row) => row.posture === "blocked") ? "Blocked" : "Ready";
          }},
          launchStartDecisionPostureFromStatus(status) {{
            return String(status || "").toLowerCase().includes("blocked") ? "blocked" : "ready";
          }},
          launchStartDecisionWorstPosture(postures) {{
            return postures.includes("blocked") ? "blocked" : "ready";
          }},
        }});

        const pipelineGate = launchModule.launchButtonGate("pipeline-start-button");
        const rerunPlanOnlyGate = launchModule.launchButtonGate("rerun-plan-only-button");
        const rerunDryRunGate = launchModule.launchButtonGate("rerun-dry-run-button");
        const rerunGate = launchModule.launchButtonGate("rerun-start-button");
        process.stdout.write(JSON.stringify({{
          pipelineGate,
          rerunPlanOnlyGate,
          rerunDryRunGate,
          rerunGate,
          decisionRequestCount: decisionRequests.length,
          decisionRequests,
          rerunRequests,
        }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-command-buttons-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch command buttons smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def _run_launch_start_request_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch start request smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(START_REQUEST_JS)!r}, "utf8");
        const fields = {{
          "pipeline-start-mode": {{ value: "continuous" }},
          "pipeline-start-single-file": {{ value: "C:/Source/Movie.mkv" }},
          "pipeline-start-sleep": {{ value: "7" }},
          "pipeline-start-schedule-override": {{ value: "run_once" }},
          "pipeline-start-show-config": {{ checked: true }},
          "pipeline-start-show-console": {{ checked: false }},
          "rerun-start-csv-path": {{ value: "C:/rerun.csv" }},
          "rerun-scope-enabled-only": {{ checked: true }},
          "rerun-scope-skip-blocked": {{ checked: true }},
          "rerun-scope-skip-warning-rows": {{ checked: false }},
          "rerun-scope-first-n": {{ value: "5" }},
          "rerun-scope-issue-filter": {{ value: "audio" }},
          "rerun-scope-bucket-filter": {{ value: "movie" }},
          "rerun-preview-limit": {{ value: "25" }},
          "rerun-start-show-console": {{ checked: true }},
          "queue-filter-text": {{ value: "visible-only" }},
          "queue-selected-row": {{ value: "C:/Other/Selected.mkv" }},
        }};
        const context = {{ window: {{}} }};
        context.window.window = context.window;
        vm.createContext(context);
        vm.runInContext(source, context);

        const startRequestModule = context.window.__launchStartRequestModule.createLaunchStartRequestModule({{
          byId(id) {{ return fields[id] || null; }},
        }});
        const pipelineRequest = startRequestModule.collectPipelineStartRequest();
        const rerunPlanOnly = startRequestModule.collectRerunStartRequest({{ plan_only: true }});
        const rerunDryRun = startRequestModule.collectRerunStartRequest({{ dry_run: true }});
        const rerunLive = startRequestModule.collectRerunStartRequest({{ dry_run: false }});
        process.stdout.write(JSON.stringify({{ pipelineRequest, rerunPlanOnly, rerunDryRun, rerunLive }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-start-request-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch start request smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def _run_launch_preflight_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch preflight smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(PREFLIGHT_JS)!r}, "utf8");
        const text = {{}};
        const elements = {{
          "launch-backend-preflight-status": {{ dataset: {{}} }},
          "launch-backend-preflight-summary": {{}},
          "launch-backend-preflight-detail": {{}},
        }};
        const domNodes = {{}};
        function makeElement(tagName) {{
          return {{
            tagName,
            className: "",
            dataset: {{}},
            attributes: {{}},
            children: [],
            textContent: "",
            setAttribute(name, value) {{ this.attributes[name] = String(value); }},
            appendChild(child) {{ this.children.push(child); }},
            replaceChildren(...children) {{
              this.children = children;
              this.textContent = children.map((child) => child.textContent || "").join(" ");
            }},
            remove() {{
              this.removed = true;
              if (domNodes[".launch-preflight-startup-alert"] === this) delete domNodes[".launch-preflight-startup-alert"];
            }},
          }};
        }}
        domNodes[".topbar"] = {{
          insertAdjacentElement(position, node) {{
            this.insertedPosition = position;
            this.inserted = node;
            domNodes[".launch-preflight-startup-alert"] = node;
          }},
        }};
        const context = {{
          window: {{}},
          document: {{
            createElement: makeElement,
            querySelector(selector) {{ return domNodes[selector] || null; }},
          }},
          URLSearchParams,
        }};
        context.window.window = context.window;
        context.window.document = context.document;
        vm.createContext(context);
        vm.runInContext(source, context);

        const encoderCapabilityDetail = {{
          schema_version: "settings_encoder_capability_report.v1",
          read_only: true,
          active_encoders: ["libaom-av1"],
          available_inactive_encoders: ["av1_nvenc"],
          activation_unknown_encoders: [],
          hardware_runtime_verified_encoders: [],
          hardware_runtime_skipped_encoders: ["av1_nvenc"],
          active_hardware_runtime_unverified_encoders: ["av1_nvenc"],
        }};
        const encoderCapabilityCheck = {{
          key: "encoder_capability_report",
          label: "Encoder capability evidence",
          status: "ready",
          evidence: "active_count=1; inactive_available_count=1",
          action: "Review inactive hardware encoder rows before enabling new families.",
          detail: [encoderCapabilityDetail],
        }};

        const fetchUrls = [];
        const factory = context.window.__launchViewPreflightModule.createLaunchPreflightModule;
        const launchPreflightModule = factory({{
          apiGet(url) {{
            fetchUrls.push(url);
            const query = new URLSearchParams(url.split("?")[1] || "");
            const target = query.get("target") || "unknown";
            const request = Object.fromEntries(query.entries());
            delete request.target;
            return Promise.resolve({{
              target,
              status: "ready",
              request,
              checks: [
                {{ key: `${{target}}-${{request.dry_run || "na"}}`, label: "Ready check", status: "ready", evidence: "ok", action: "No action." }},
                encoderCapabilityCheck,
              ],
            }});
          }},
          byId(id) {{ return elements[id] || null; }},
          clearRows() {{}},
          collectPipelineStartRequest() {{ return {{ mode: "once", sleep_seconds: 30, schedule_override: "" }}; }},
          collectRerunStartRequest(options = {{}}) {{ return {{ csv_path: "C:/rerun.csv", dry_run: Boolean(options.dry_run), plan_only: Boolean(options.plan_only), stage_mode: "copy", original_mode: "keep", return_mode: "park" }}; }},
          launchPreflightRequestMatches(payload, request, keys) {{
            return keys.every((key) => String(payload.request?.[key] ?? "") === String(request?.[key] ?? ""));
          }},
          setText(id, value) {{ text[id] = String(value); }},
          updateTableStatusLegend() {{}},
        }});

        (async () => {{
          launchPreflightModule.renderAllLaunchPreflights();
          const renderFetchCount = fetchUrls.length;
          await launchPreflightModule.refreshLaunchBackendPreflight();
          const payloads = launchPreflightModule.getLastLaunchBackendPreflightPayloads();
          const rows = launchPreflightModule.launchBackendPreflightRows(payloads);
          const refreshInfo = launchPreflightModule.getLastLaunchBackendPreflightRefreshInfo();
          const stagedSummary = text["launch-backend-preflight-summary"];

          const emptyCsvFetchUrls = [];
          const emptyCsvText = {{}};
          const emptyCsvElements = {{
            "launch-backend-preflight-status": {{ dataset: {{}} }},
            "launch-backend-preflight-summary": {{}},
            "launch-backend-preflight-detail": {{}},
          }};
          const emptyCsvModule = factory({{
            apiGet(url) {{
              emptyCsvFetchUrls.push(url);
              const query = new URLSearchParams(url.split("?")[1] || "");
              const target = query.get("target") || "unknown";
              const request = Object.fromEntries(query.entries());
              delete request.target;
              return Promise.resolve({{
                target,
                status: "ready",
                request,
                checks: [
                  {{ key: `${{target}}-ready`, label: "Ready check", status: "ready", evidence: "ok", action: "No action." }},
                  encoderCapabilityCheck,
                ],
              }});
            }},
            byId(id) {{ return emptyCsvElements[id] || null; }},
            clearRows() {{}},
            collectPipelineStartRequest() {{ return {{ mode: "once", sleep_seconds: 30, schedule_override: "" }}; }},
            collectRerunStartRequest(options = {{}}) {{ return {{ csv_path: "", dry_run: Boolean(options.dry_run), plan_only: Boolean(options.plan_only), stage_mode: "copy", original_mode: "keep", return_mode: "park" }}; }},
            launchPreflightRequestMatches(payload, request, keys) {{
              return keys.every((key) => String(payload.request?.[key] ?? "") === String(request?.[key] ?? ""));
            }},
            setText(id, value) {{ emptyCsvText[id] = String(value); }},
            updateTableStatusLegend() {{}},
          }});
          await emptyCsvModule.refreshLaunchBackendPreflight();
          const emptyCsvPayloads = emptyCsvModule.getLastLaunchBackendPreflightPayloads();
          const emptyCsvRows = emptyCsvModule.launchBackendPreflightRows(emptyCsvPayloads);
          const emptyCsvRefreshInfo = emptyCsvModule.getLastLaunchBackendPreflightRefreshInfo();
          const emptyCsvSummary = emptyCsvText["launch-backend-preflight-summary"];
          const emptyCsvCandidates = emptyCsvModule.launchBackendPreflightCandidateRequests().map((item) => ({{
            key: item.key,
            active: item.active,
            reason: item.inactive_reason || item.scope_reason,
          }}));
          const poisonPayloads = [
            {{
              target: "pipeline",
              _frontend_target_label: "Pipeline",
              _frontend_preflight_active: true,
              _frontend_preflight_included: true,
              status: "ready",
              checks: [{{ key: "pipeline-ready", label: "Pipeline ready", status: "ready", evidence: "ok", action: "No action." }}],
            }},
            {{
              target: "rerun",
              _frontend_target_label: "CSV Rerun Start",
              _frontend_preflight_active: false,
              _frontend_preflight_included: false,
              status: "blocked",
              checks: [{{ key: "csv_path", label: "CSV path", status: "blocked", evidence: "missing", action: "Stage a CSV." }}],
            }},
          ];
          const activeWorkAlertPayloads = [
            {{
              target: "pipeline",
              _frontend_target_label: "Pipeline",
              _frontend_preflight_active: true,
              _frontend_preflight_included: true,
              status: "blocked",
              can_request_start: false,
              checks: [{{ key: "active_work", label: "Active work guard", status: "blocked", evidence: "active worker is running", action: "Wait for active work to finish." }}],
            }},
          ];
          emptyCsvModule.renderLaunchBackendPreflight(activeWorkAlertPayloads);
          const activeWorkAlertSuppressed = !domNodes[".launch-preflight-startup-alert"];
          const alertPayloads = [
            {{
              target: "pipeline",
              _frontend_target_label: "Pipeline",
              _frontend_preflight_active: true,
              _frontend_preflight_included: true,
              status: "blocked",
              can_request_start: false,
              checks: [{{ key: "config_identity", label: "Active config identity", status: "blocked", evidence: "config is not verified", action: "Restore a verified operator PSD1." }}],
            }},
          ];
          emptyCsvModule.renderLaunchBackendPreflight(alertPayloads);
          const blockedAlert = domNodes[".launch-preflight-startup-alert"];
          const blockedAlertText = blockedAlert ? blockedAlert.textContent : "";
          const blockedAlertState = blockedAlert?.dataset?.state || "";
          const blockedAlertRole = blockedAlert?.attributes?.role || "";
          const blockedAlertLive = blockedAlert?.attributes?.["aria-live"] || "";
          emptyCsvModule.renderLaunchBackendPreflight(poisonPayloads);
          const alertClearedByReadyPipeline = !domNodes[".launch-preflight-startup-alert"];
          process.stdout.write(JSON.stringify({{
            renderFetchCount,
            fetchUrls,
            labels: rows.map((row) => row.targetLabel),
            statusText: text["launch-backend-preflight-status"],
            statusState: elements["launch-backend-preflight-status"].dataset.state,
            refreshInfo,
            stagedSummary,
            emptyCsvFetchUrls,
            emptyCsvLabels: emptyCsvRows.map((row) => row.targetLabel),
            emptyCsvStatusText: emptyCsvText["launch-backend-preflight-status"],
            emptyCsvRefreshInfo,
            emptyCsvSummary,
            emptyCsvCandidates,
            poisonStatus: emptyCsvModule.launchBackendPreflightOverallStatus(poisonPayloads),
            poisonRows: emptyCsvModule.launchBackendPreflightRows(poisonPayloads).map((row) => row.targetLabel + ":" + row.posture),
            poisonScopeLabel: emptyCsvModule.launchBackendPreflightScopeLabel(poisonPayloads),
            activeWorkAlertSuppressed,
            blockedAlertText,
            blockedAlertState,
            blockedAlertRole,
            blockedAlertLive,
            alertClearedByReadyPipeline,
          }}));
        }})().catch((error) => {{
          console.error(error && error.stack ? error.stack : String(error));
          process.exit(1);
        }});
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-preflight-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch preflight smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def _run_launch_controller_state_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch controller state smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(CONTROLLER_STATE_JS)!r}, "utf8");
        const context = {{ window: {{}} }};
        context.window.window = context.window;
        vm.createContext(context);
        vm.runInContext(source, context);

        const launchControllerStateModule = context.window.__launchControllerStateModule.createLaunchControllerStateModule();
        const staleSnapshot = {{ pipeline_state: "idle", progress: {{ CurrentStage: "encoding", Status: "last update old" }} }};
        const stuckSnapshot = {{ pipeline_state: "idle", progress: {{ CurrentStage: "encoding", Status: "stuck without active worker" }} }};
        const activeClose = {{ safe_to_close: false, active_work: true, state: "running" }};
        process.stdout.write(JSON.stringify({{
          staleIsStuck: launchControllerStateModule.pipelineProgressIsStuck(staleSnapshot),
          staleIsStale: launchControllerStateModule.pipelineProgressIsStale(staleSnapshot),
          staleController: launchControllerStateModule.pipelineControllerState(staleSnapshot, {{ safe_to_close: true }}, false, false),
          staleSummary: launchControllerStateModule.pipelineControllerStageSummary(staleSnapshot, {{ safe_to_close: true }}, false, false),
          stuckIsStuck: launchControllerStateModule.pipelineProgressIsStuck(stuckSnapshot),
          activeIsActive: launchControllerStateModule.launchPipelineIsActive(staleSnapshot, activeClose),
        }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-controller-state-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch controller state smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def _run_launch_compact_gate_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch compact gate smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(LAUNCH_SCOPE_JS)!r}, "utf8");
        const context = {{
          window: {{}},
          document: {{ querySelectorAll() {{ return []; }} }},
        }};
        context.window.window = context.window;
        context.window.document = context.document;
        vm.createContext(context);
        vm.runInContext(source, context);

        const factory = context.window.__launchViewScopeModule.createLaunchScopeModule;
        const activePreflight = {{
          target: "pipeline",
          status: "blocked",
          can_request_start: false,
          checks: [
            {{
              key: "active_work",
              label: "Active work guard",
              status: "blocked",
              evidence: "A normal run is already active.",
              action: "Wait for active work to finish.",
            }},
          ],
        }};
        const hardBlockPreflight = {{
          target: "pipeline",
          status: "blocked",
          can_request_start: false,
          checks: [
            {{
              key: "config_identity",
              label: "Active config identity",
              status: "blocked",
              evidence: "Config is not verified.",
              action: "Restore a verified operator PSD1.",
            }},
          ],
        }};
        let currentPreflight = activePreflight;

        function preflightRows(items) {{
          return (Array.isArray(items) ? items : []).flatMap((payload) => {{
            const target = payload.target || "pipeline";
            return (Array.isArray(payload.checks) ? payload.checks : []).map((check, index) => ({{
              key: `${{target}}:${{check.key || check.label || index}}`,
              target,
              targetLabel: "Pipeline",
              checkKey: check.key || "",
              check: check.label || check.key || "Check",
              posture: check.status || "unknown",
              evidence: check.evidence || "",
              action: check.action || "",
              detail: [],
              payload,
            }}));
          }});
        }}

        const launchScopeModule = factory({{
          collectPipelineStartRequest() {{ return {{ mode: "once", schedule_override: "" }}; }},
          getCommandHistory() {{ return [{{ command: "pipeline.start", ok: true, result: "ok", message: "Started" }}]; }},
          getLastQueueRows() {{ return [{{ source_path: "C:/Source/Movie.mkv", route_decision_summary: "Remux", status: "ready" }}]; }},
          getLastQueuePayload() {{ return {{ schema_version: "queue.v1", blocked_row_count: 0, invalid_row_count: 0 }}; }},
          getLastLaunchBackendPreflightRefreshInfo() {{ return {{ fetch_failure_count: 0 }}; }},
          isLaunchCommand(entry) {{ return String(entry?.command || "") === "pipeline.start"; }},
          launchBackendPreflightPayloadForTarget(target) {{ return String(target || "").toLowerCase() === "pipeline" ? currentPreflight : null; }},
          launchBackendPreflightRows: preflightRows,
          launchBackendPreflightOverallStatus(items) {{
            return (Array.isArray(items) ? items : []).some((item) => String(item.status || "").toLowerCase() === "blocked") ? "Blocked" : "Ready";
          }},
          launchBackendPreflightSummaryLines() {{ return ["Backend preflight summary."]; }},
          launchCommandReviewRows() {{ return [{{ posture: "ready" }}]; }},
          launchCommandReviewStatus() {{ return "Ready"; }},
          launchCommandReviewSummaryLines() {{ return []; }},
          launchPolicyBoundaryRows() {{ return []; }},
          launchPolicyBoundarySummaryLines() {{ return []; }},
          launchReadinessLines() {{ return ["Launch readiness lines."]; }},
          launchSettingsIntentPayload(payload) {{ return payload && typeof payload === "object" ? payload : {{}}; }},
          launchSettingsIntentRows() {{ return [{{ key: "saved-settings", posture: "ready" }}]; }},
          launchSettingsIntentSummaryLines() {{ return ["Settings ready."]; }},
          launchSettingsWorkspace() {{ return {{ schema_version: "settings.v1" }}; }},
          launchTimingStatus(payload) {{ return payload?.closeReadiness?.active_work ? "Active work" : "Ready"; }},
          launchTimingTrustLines() {{ return ["Timing lines."]; }},
          queueLaunchDecisionRows() {{ return [{{ key: "backend-launch-preflight", posture: "Blocked" }}]; }},
          queueLaunchDecisionStatus() {{ return "Do not launch"; }},
          queueLaunchDecisionSummaryLines() {{ return ["Queue decision summary."]; }},
        }});

        const activeContext = {{
          closeReadiness: {{ safe_to_close: false, active_work: true }},
          snapshot: {{ pipeline_state: "running" }},
          schedule: {{ enabled: false }},
        }};
        const activeRows = launchScopeModule.launchCompactGateRows({{ mode: "once", schedule_override: "" }}, activeContext);
        const activeMap = Object.fromEntries(activeRows.map((row) => [row.key, row]));

        currentPreflight = hardBlockPreflight;
        const blockedContext = {{
          closeReadiness: {{ safe_to_close: true, active_work: false }},
          snapshot: {{ pipeline_state: "idle" }},
          schedule: {{ enabled: false }},
        }};
        const blockedRows = launchScopeModule.launchCompactGateRows({{ mode: "once", schedule_override: "" }}, blockedContext);
        const blockedMap = Object.fromEntries(blockedRows.map((row) => [row.key, row]));

        process.stdout.write(JSON.stringify({{
          activeOverall: launchScopeModule.launchCompactGateOverallStatus(activeRows),
          activeBackendStatus: activeMap.backend?.status,
          activeBackendValue: activeMap.backend?.value,
          activeQueueStatus: activeMap.queue?.status,
          activeScheduleStatus: activeMap.schedule?.status,
          activeWorkStatus: activeMap.active?.status,
          blockedOverall: launchScopeModule.launchCompactGateOverallStatus(blockedRows),
          blockedBackendStatus: blockedMap.backend?.status,
          blockedBackendValue: blockedMap.backend?.value,
        }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-compact-gate-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch compact gate smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def _run_launch_readiness_recovery_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch readiness recovery smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        function makeElement(tag = "div") {{
          return {{
            tagName: String(tag).toUpperCase(),
            children: [],
            dataset: {{}},
            attributes: {{}},
            hidden: false,
            className: "",
            title: "",
            type: "",
            _text: "",
            set textContent(value) {{ this._text = String(value); }},
            get textContent() {{
              return this._text || this.children.map((child) => child.textContent || "").join("");
            }},
            appendChild(child) {{ this.children.push(child); return child; }},
            replaceChildren(...items) {{ this.children = items; this._text = ""; }},
            setAttribute(name, value) {{ this.attributes[name] = String(value); }},
          }};
        }}

        const elements = {{
          "launch-readiness-status": makeElement(),
          "launch-readiness": makeElement(),
          "launch-readiness-actions": makeElement(),
          "launch-readiness-action-status": makeElement(),
          "launch-timing-status": makeElement(),
          "launch-timing": makeElement(),
        }};
        const context = {{
          window: {{}},
          document: {{
            getElementById(id) {{ return elements[id] || null; }},
            createElement(tag) {{ return makeElement(tag); }},
          }},
          setText(id, value) {{
            if (!elements[id]) elements[id] = makeElement();
            elements[id].textContent = String(value);
          }},
        }};
        context.window.window = context.window;
        context.window.document = context.document;
        context.window.mediaPipelineDom = {{
          byId(id) {{ return elements[id] || null; }},
        }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({str(LAUNCH_READINESS_JS)!r}, "utf8"), context);

        context.window.mediaPipelineLaunchReadinessView.renderLaunchReadiness({{
          backendReadiness: {{
            evidence_authority: "backend",
            display_status: "Blocked",
            can_request_start: false,
            start_route: "/api/pipeline/start",
            non_ready_checks: [
              {{
                key: "autonomy_health",
                recovery_actions: [
                  {{
                    kind: "archive_state_journals",
                    label: "Archive Event Journal",
                    route: "/api/maintenance/archive-state-journals",
                    request: {{ confirm_archive: true, reason: "launch recovery" }},
                    requires_confirmation: true,
                  }},
                  {{
                    kind: "drain_pending_pushes",
                    label: "Drain Parked Outputs",
                    route: "/api/pipeline/start",
                    request: {{ mode: "drain_pending_pushes" }},
                    requires_confirmation: true,
                  }},
                ],
              }},
            ],
          }},
        }});

        const buttons = elements["launch-readiness-actions"].children.map((button) => ({{
          text: button.textContent,
          kind: button.dataset.launchRecoveryAction,
          route: button.dataset.launchRecoveryRoute,
          request: JSON.parse(button.dataset.launchRecoveryRequest || "{{}}"),
          requiresConfirmation: button.dataset.requiresConfirmation,
        }}));
        process.stdout.write(JSON.stringify({{
          status: elements["launch-readiness-status"].textContent,
          actionsHidden: elements["launch-readiness-actions"].hidden,
          actionStatus: elements["launch-readiness-action-status"].textContent,
          buttons,
        }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-readiness-recovery-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch readiness recovery smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


class WebViewLaunchCommandButtonsSmoke(unittest.TestCase):
    def test_rerun_gates_ignore_pipeline_only_start_decision_blockers(self) -> None:
        result = _run_launch_command_buttons_smoke()

        self.assertTrue(result["pipelineGate"]["blocked"])
        self.assertFalse(result["rerunPlanOnlyGate"]["blocked"])
        self.assertFalse(result["rerunDryRunGate"]["blocked"])
        self.assertFalse(result["rerunGate"]["blocked"])
        self.assertEqual(result["decisionRequestCount"], 1)
        self.assertTrue(result["decisionRequests"][0]["pipeline_only_blocker"])
        self.assertTrue(any(item["plan_only"] for item in result["rerunRequests"]))
        self.assertTrue(any(item["dry_run"] for item in result["rerunRequests"]))
        self.assertTrue(any(not item["dry_run"] for item in result["rerunRequests"]))
        self.assertIn("Plan CSV Rerun", result["rerunPlanOnlyGate"]["reason"])
        self.assertIn("Preview CSV Rerun", result["rerunDryRunGate"]["reason"])
        self.assertIn("Start CSV Rerun", result["rerunGate"]["reason"])

    def test_start_request_collectors_keep_queue_scope_out_and_support_rerun_dry_run(self) -> None:
        result = _run_launch_start_request_smoke()
        pipeline_request = result["pipelineRequest"]

        self.assertEqual(pipeline_request["mode"], "continuous")
        self.assertEqual(pipeline_request["single_file"], "C:/Source/Movie.mkv")
        self.assertEqual(pipeline_request["sleep_seconds"], 7)
        self.assertEqual(pipeline_request["schedule_override"], "run_once")
        self.assertNotIn("queue_filter", pipeline_request)
        self.assertNotIn("selected_row", pipeline_request)
        self.assertNotIn("selected_path", pipeline_request)
        self.assertTrue(result["rerunPlanOnly"]["plan_only"])
        self.assertFalse(result["rerunPlanOnly"]["dry_run"])
        self.assertTrue(result["rerunDryRun"]["dry_run"])
        self.assertFalse(result["rerunDryRun"]["plan_only"])
        self.assertFalse(result["rerunLive"]["dry_run"])
        self.assertFalse(result["rerunLive"]["plan_only"])
        self.assertEqual(result["rerunDryRun"]["stage_mode"], "copy")
        self.assertEqual(result["rerunDryRun"]["original_mode"], "keep")
        self.assertEqual(result["rerunDryRun"]["return_mode"], "park")
        self.assertEqual(
            result["rerunDryRun"]["scope"],
            {
                "enabled_only": True,
                "skip_blocked": True,
                "skip_warning_rows": False,
                "first_n": 5,
                "issue_filter": "audio",
                "bucket_filter": "movie",
                "preview_limit": 25,
            },
        )

    def test_backend_preflight_refresh_is_explicit_and_splits_csv_preview_from_start(self) -> None:
        result = _run_launch_preflight_smoke()

        self.assertEqual(result["renderFetchCount"], 0)
        self.assertEqual(len(result["fetchUrls"]), 4)
        self.assertTrue(any("plan_only=true" in item for item in result["fetchUrls"]))
        self.assertTrue(any("dry_run=true" in item for item in result["fetchUrls"]))
        self.assertTrue(any("dry_run=false" in item for item in result["fetchUrls"]))
        self.assertIn("CSV Rerun Plan Only", result["labels"])
        self.assertIn("CSV Rerun Preview", result["labels"])
        self.assertIn("CSV Rerun Start", result["labels"])
        self.assertEqual(result["statusText"], "Ready")
        self.assertEqual(result["statusState"], "ready")
        self.assertEqual(result["refreshInfo"]["candidate_request_count"], 4)
        self.assertEqual(result["refreshInfo"]["skipped_request_count"], 0)
        self.assertIn("Status scope: active targets only", result["stagedSummary"])
        self.assertIn("Launch backend preflight by active target", result["stagedSummary"])
        self.assertIn("Encoder activation evidence: active=1 (libaom-av1); available inactive=1 (av1_nvenc); activation unknown=0.", result["stagedSummary"])
        self.assertIn("Hardware runtime proof: verified=0; skipped=1 (av1_nvenc); active unverified=1 (av1_nvenc).", result["stagedSummary"])
        self.assertIn("Active hardware encoders without runtime proof remain review-only: av1_nvenc.", result["stagedSummary"])
        self.assertIn("WebView does not enable hardware families", result["stagedSummary"])
        self.assertEqual(len(result["emptyCsvFetchUrls"]), 1)
        self.assertIn("target=pipeline", result["emptyCsvFetchUrls"][0])
        self.assertFalse(any("target=rerun" in item for item in result["emptyCsvFetchUrls"]))
        self.assertEqual(sorted(set(result["emptyCsvLabels"])), ["Pipeline"])
        self.assertEqual(result["emptyCsvStatusText"], "Ready")
        self.assertEqual(result["emptyCsvRefreshInfo"]["candidate_request_count"], 4)
        self.assertEqual(result["emptyCsvRefreshInfo"]["skipped_request_count"], 3)
        self.assertEqual(
            [item["key"] for item in result["emptyCsvRefreshInfo"]["skipped_targets"]],
            ["rerun-live", "rerun-preview", "rerun-plan-only"],
        )
        self.assertIn("Pipeline backend preflight", result["emptyCsvSummary"])
        self.assertIn("Inactive targets skipped: CSV Rerun Start: CSV path is not staged.", result["emptyCsvSummary"])
        self.assertIn("Encoder activation evidence: active=1 (libaom-av1); available inactive=1 (av1_nvenc); activation unknown=0.", result["emptyCsvSummary"])
        self.assertIn("Hardware runtime proof: verified=0; skipped=1 (av1_nvenc); active unverified=1 (av1_nvenc).", result["emptyCsvSummary"])
        self.assertEqual(
            {item["key"]: item["active"] for item in result["emptyCsvCandidates"]},
            {"pipeline": True, "rerun-live": False, "rerun-preview": False, "rerun-plan-only": False},
        )
        self.assertEqual(result["poisonStatus"], "Ready")
        self.assertEqual(result["poisonRows"], ["Pipeline:ready"])
        self.assertEqual(result["poisonScopeLabel"], "Pipeline backend preflight")
        self.assertTrue(result["activeWorkAlertSuppressed"])
        self.assertIn("Pipeline launch blocked by backend preflight", result["blockedAlertText"])
        self.assertIn("Active config identity", result["blockedAlertText"])
        self.assertIn("config is not verified", result["blockedAlertText"])
        self.assertIn("Restore a verified operator PSD1.", result["blockedAlertText"])
        self.assertEqual(result["blockedAlertState"], "blocked")
        self.assertEqual(result["blockedAlertRole"], "alert")
        self.assertEqual(result["blockedAlertLive"], "assertive")
        self.assertTrue(result["alertClearedByReadyPipeline"])

    def test_active_work_compact_gate_renders_active_instead_of_will_fail(self) -> None:
        result = _run_launch_compact_gate_smoke()

        self.assertEqual(result["activeOverall"], "Active")
        self.assertEqual(result["activeBackendStatus"], "running")
        self.assertEqual(result["activeBackendValue"], "Active")
        self.assertEqual(result["activeQueueStatus"], "running")
        self.assertEqual(result["activeScheduleStatus"], "running")
        self.assertEqual(result["activeWorkStatus"], "running")
        self.assertEqual(result["blockedOverall"], "Will Fail")
        self.assertEqual(result["blockedBackendStatus"], "blocked")
        self.assertEqual(result["blockedBackendValue"], "Will Fail")

    def test_stale_progress_does_not_count_as_stuck_without_backend_stuck_signal(self) -> None:
        result = _run_launch_controller_state_smoke()

        self.assertFalse(result["staleIsStuck"])
        self.assertTrue(result["staleIsStale"])
        self.assertEqual(result["staleController"], "stale")
        self.assertIn("Stale progress evidence", result["staleSummary"])
        self.assertTrue(result["stuckIsStuck"])
        self.assertTrue(result["activeIsActive"])

    def test_launch_readiness_renders_backend_recovery_actions(self) -> None:
        result = _run_launch_readiness_recovery_smoke()

        self.assertEqual(result["status"], "Blocked")
        self.assertFalse(result["actionsHidden"])
        self.assertIn("Backend recovery actions", result["actionStatus"])
        routes = {button["kind"]: button["route"] for button in result["buttons"]}
        self.assertEqual(routes["archive_state_journals"], "/api/maintenance/archive-state-journals")
        self.assertEqual(routes["drain_pending_pushes"], "/api/pipeline/start")
        archive = next(button for button in result["buttons"] if button["kind"] == "archive_state_journals")
        self.assertEqual(archive["request"], {"confirm_archive": True, "reason": "launch recovery"})
        self.assertEqual(archive["requiresConfirmation"], "true")

    def test_launch_recovery_archive_button_posts_allowlisted_backend_route(self) -> None:
        launch_source = LAUNCH_VIEW_JS.read_text(encoding="utf-8")
        readiness_source = LAUNCH_READINESS_JS.read_text(encoding="utf-8")
        diagnostics_source = PAGE_DIAGNOSTICS_HTML.read_text(encoding="utf-8")

        self.assertIn("[data-launch-recovery-action]", launch_source)
        self.assertIn('document.addEventListener("click"', launch_source)
        self.assertIn("/api/maintenance/archive-state-journals", launch_source)
        self.assertIn("confirm_archive: true", launch_source)
        self.assertIn("archive_state_journals", readiness_source)
        self.assertIn("launchRecoveryAction", readiness_source)
        self.assertIn("launch-readiness-actions", diagnostics_source)


if __name__ == "__main__":
    unittest.main()
