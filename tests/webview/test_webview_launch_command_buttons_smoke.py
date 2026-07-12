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
LAUNCH_COMPACT_GATE_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "scope" / "compactGate.js"
PAGE_LAUNCH_HTML = ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-launch.html"
PAGE_QUEUE_HTML = ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-queue.html"
PAGE_DIAGNOSTICS_HTML = ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-diagnostics.html"
PREFLIGHT_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launchView.preflight.js"
PILOT_READINESS_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "preflight" / "pilotReadiness.js"
START_REQUEST_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "startRequest.js"
QUEUE_RERUN_REQUEST_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "queue" / "rerunRequest.js"
LAUNCH_VIEW_ASSET_NAMES = (
    "launch/rerunEvidence.js",
    "launch/rerunPresentation.js",
    "launch/commandOrchestration.js",
    "launchView.js",
)


def _launch_view_bundle() -> str:
    assets_root = ROOT / "apps" / "desktop" / "webview" / "static" / "assets"
    return "\n".join((assets_root / name).read_text(encoding="utf-8") for name in LAUNCH_VIEW_ASSET_NAMES)


def _run_launch_command_buttons_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch command buttons smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(COMMAND_BUTTONS_JS)!r}, "utf8");
        function makeButton(action) {{
          return {{
            dataset: {{ controlAction: action }},
            disabled: false,
            title: "",
            textContent: "",
            className: "",
            classList: {{ contains() {{ return false; }} }},
            setAttribute(name, value) {{ this[name] = String(value); }},
            closest() {{ return null; }},
          }};
        }}
        const controlButtons = {{
          pause: makeButton("pause"),
          rescan: makeButton("rescan"),
          stop: makeButton("stop"),
          kill: makeButton("kill"),
        }};
        const context = {{
          window: {{}},
          document: {{
            querySelectorAll(selector) {{
              if (selector === '[data-control-action="pause"]') return [controlButtons.pause];
              if (selector === "[data-control-action]") return Object.values(controlButtons);
              return [];
            }},
          }},
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
        ];
        function valuesMatch(left, right) {{
          return JSON.stringify(left) === JSON.stringify(right);
        }}
        const launchModule = factory({{
          collectPipelineStartRequest() {{
            return {{ mode: "continuous", sleep_seconds: 30, schedule_override: "", single_file: "", pipeline_only_blocker: true }};
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
        const missingPreflightModule = factory({{
          collectPipelineStartRequest() {{
            return {{ mode: "once", sleep_seconds: 30, schedule_override: "", single_file: "" }};
          }},
          launchBackendPreflightPayloadForTarget() {{ return null; }},
          launchStartDecisionRows() {{
            throw new Error("Pipeline button gate should not consult local start-decision rows.");
          }},
        }});
        const missingPreflightGate = missingPreflightModule.launchButtonGate("pipeline-start-button");
        const controlText = {{}};
        const csvControlModule = factory({{
          byId() {{ return null; }},
          launchPipelineIsActive() {{ return true; }},
          launchActiveJobKind() {{ return "rerun_csv"; }},
          launchRerunCsvIsActive() {{ return true; }},
          launchPauseRequested() {{ return false; }},
          pipelineProgressIsStuck() {{ return false; }},
          pipelineProgressIsStale() {{ return false; }},
          renderPipelineControllerStatus() {{}},
          setText(id, value) {{ controlText[id] = String(value); }},
          syncPipelineScopeControls() {{}},
        }});
        csvControlModule.updateLaunchCommandButtonStates({{ active_work: [{{ job_kind: "rerun_csv" }}] }}, {{}});
        process.stdout.write(JSON.stringify({{
          pipelineGate,
          missingPreflightGate,
          csvControl: {{
            pauseDisabled: controlButtons.pause.disabled,
            pauseTitle: controlButtons.pause.title,
            rescanDisabled: controlButtons.rescan.disabled,
            stopDisabled: controlButtons.stop.disabled,
            stopTitle: controlButtons.stop.title,
            killDisabled: controlButtons.kill.disabled,
          }},
          decisionRequestCount: decisionRequests.length,
          decisionRequests,
        }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-command-buttons-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            capture_output=True,
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
        raise unittest.SkipTest("Node.js is required for the launch/queue request smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const launchSource = fs.readFileSync({str(START_REQUEST_JS)!r}, "utf8");
        const queueRerunSource = fs.readFileSync({str(QUEUE_RERUN_REQUEST_JS)!r}, "utf8");
        const fields = {{
          "pipeline-start-mode": {{ value: "continuous" }},
          "pipeline-start-single-file": {{ value: "C:/Source/Movie.mkv" }},
          "pipeline-start-sleep": {{ value: "7" }},
          "pipeline-start-schedule-override": {{ value: "run_once" }},
          "pipeline-start-show-config": {{ checked: true }},
          "pipeline-start-show-console": {{ checked: false }},
          "rerun-start-csv-path": {{ value: "C:/rerun.csv" }},
          "rerun-start-execution-mode": {{ value: "windowed" }},
          "rerun-start-window-size": {{ value: "3" }},
          "rerun-start-destination-mode": {{ value: "pending_publish" }},
          "rerun-start-collision-policy": {{ value: "suffix" }},
          "rerun-start-confirm-source-overwrite": {{ checked: false }},
          "rerun-scope-enabled-only": {{ checked: true }},
          "rerun-scope-skip-blocked": {{ checked: true }},
          "rerun-scope-skip-warning-rows": {{ checked: false }},
          "rerun-scope-first-n": {{ value: "5" }},
          "rerun-scope-issue-filter": {{ options: [{{ value: "audio", selected: true }}, {{ value: "subtitle", selected: false }}] }},
          "rerun-scope-bucket-filter": {{ options: [{{ value: "movie", selected: true }}] }},
          "rerun-preview-limit": {{ value: "25" }},
          "queue-filter-text": {{ value: "visible-only" }},
          "queue-selected-row": {{ value: "C:/Other/Selected.mkv" }},
        }};
        const context = {{ window: {{}} }};
        context.window.window = context.window;
        vm.createContext(context);
        vm.runInContext(launchSource, context);
        vm.runInContext(queueRerunSource, context);

        const startRequestModule = context.window.__launchStartRequestModule.createLaunchStartRequestModule({{
          byId(id) {{ return fields[id] || null; }},
        }});
        const queueRerunRequestModule = context.window.__queueRerunRequestModule.createQueueRerunRequestModule({{
          byId(id) {{ return fields[id] || null; }},
        }});
        const pipelineRequest = startRequestModule.collectPipelineStartRequest();
        const rerunLive = queueRerunRequestModule.collectRerunStartRequest({{ dry_run: false }});
        const rerunPreview = queueRerunRequestModule.collectRerunPreviewRequest();
        fields["rerun-start-destination-mode"].value = "publish_replace_final";
        fields["rerun-start-collision-policy"].value = "replace_final";
        fields["rerun-start-confirm-source-overwrite"].checked = true;
        const rerunHighRisk = queueRerunRequestModule.collectRerunStartRequest({{ dry_run: false }});
        process.stdout.write(JSON.stringify({{ pipelineRequest, rerunLive, rerunPreview, rerunHighRisk }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-queue-request-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch/Queue request smoke failed.\n"
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

        const pilotReadinessSource = fs.readFileSync({str(PILOT_READINESS_JS)!r}, "utf8");
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
        vm.runInContext(pilotReadinessSource, context);
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
        const postCalls = [];
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
          apiPost(path, payload, options) {{
            postCalls.push({{ path, payload, timeoutMs: options?.timeoutMs || 0 }});
            return Promise.resolve({{
              ok: true,
              command: "diagnostics.encoder_capabilities.refresh",
              data: {{ launches_media_processing: false, source_media_mutation: false }},
            }});
          }},
          byId(id) {{ return elements[id] || null; }},
          clearRows() {{}},
          collectPipelineStartRequest() {{ return {{ mode: "once", sleep_seconds: 30, schedule_override: "" }}; }},
          collectRerunStartRequest(options = {{}}) {{ return {{ csv_path: "C:/rerun.csv", dry_run: Boolean(options.dry_run), plan_only: Boolean(options.plan_only), execution_mode: "one_at_a_time", destination_mode: "review_workspace", collision_policy: "suffix", window_size: 1 }}; }},
          launchPreflightRequestMatches(payload, request, keys) {{
            return keys.every((key) => String(payload.request?.[key] ?? "") === String(request?.[key] ?? ""));
          }},
          setText(id, value) {{ text[id] = String(value); }},
          updateTableStatusLegend() {{}},
        }});

        (async () => {{
          launchPreflightModule.renderAllLaunchPreflights();
          const replacementRerunPreflight = launchPreflightModule.rerunQueuePreflightLines({{
            csv_path: "C:/rerun.csv",
            dry_run: false,
            plan_only: false,
            execution_mode: "one_at_a_time",
            destination_mode: "publish_replace_final",
            collision_policy: "replace_final",
            window_size: 1,
            scope: {{ enabled_only: true, skip_blocked: false, skip_warning_rows: false, first_n: 0, issue_filters: [], bucket_filters: [] }},
            confirm_replace_final: true,
          }}).join("\\n");
          const manualKeepRerunPreflight = launchPreflightModule.rerunQueuePreflightLines({{
            csv_path: "C:/rerun.csv",
            dry_run: false,
            plan_only: false,
            execution_mode: "one_at_a_time",
            destination_mode: "publish_replace_final",
            collision_policy: "replace_final",
            window_size: 1,
            scope: {{ enabled_only: true, skip_blocked: false, skip_warning_rows: false, first_n: 0, issue_filters: [], bucket_filters: [] }},
            confirm_replace_final: true,
          }}).join("\\n");
          const renderFetchCount = fetchUrls.length;
          await launchPreflightModule.refreshLaunchBackendPreflight();
          const payloads = launchPreflightModule.getLastLaunchBackendPreflightPayloads();
          const rows = launchPreflightModule.launchBackendPreflightRows(payloads);
          const refreshInfo = launchPreflightModule.getLastLaunchBackendPreflightRefreshInfo();
          const stagedSummary = text["launch-backend-preflight-summary"];

          const emptyCsvFetchUrls = [];
          const emptyCsvPostCalls = [];
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
            apiPost(path, payload, options) {{
              emptyCsvPostCalls.push({{ path, payload, timeoutMs: options?.timeoutMs || 0 }});
              return Promise.resolve({{
                ok: true,
                command: "diagnostics.encoder_capabilities.refresh",
                data: {{ launches_media_processing: false, source_media_mutation: false }},
              }});
            }},
            byId(id) {{ return emptyCsvElements[id] || null; }},
            clearRows() {{}},
            collectPipelineStartRequest() {{ return {{ mode: "once", sleep_seconds: 30, schedule_override: "" }}; }},
            collectRerunStartRequest(options = {{}}) {{ return {{ csv_path: "", dry_run: Boolean(options.dry_run), plan_only: Boolean(options.plan_only), execution_mode: "one_at_a_time", destination_mode: "review_workspace", collision_policy: "suffix", window_size: 1 }}; }},
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
          const emptyCsvDefaultFetchUrls = emptyCsvFetchUrls.slice();
          const encoderRefreshStart = emptyCsvFetchUrls.length;
          await emptyCsvModule.refreshLaunchBackendPreflightEncoderCapability();
          const encoderRefreshFetchUrls = emptyCsvFetchUrls.slice(encoderRefreshStart);
          const encoderRefreshInfo = emptyCsvModule.getLastLaunchBackendPreflightRefreshInfo();
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
              _frontend_target_label: "Queue CSV Rerun Start",
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
              checks: [{{
                key: "autonomy_health",
                label: "Autonomy health gate",
                status: "blocked",
                evidence: "overall_status=blocked; can_start_new_work=no; blocker=autonomy_pending_manifest_untrusted; reason=Pending Publish manifest is not trusted: Current pending manifest contract invalid: pipeline_version is required and cannot be blank.",
                action: "Open Pending Publish, select the blocked row, then run Recovery Plan or Repair Manifest dry-run. If none is available, inspect docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md.",
                detail: [
                  "row_key=pending-row-1",
                  "manifest=C:/LocalBase/State/PendingServerPush/movie.manifest.json",
                  "recovery_action=pending_publish_recovery_plan: Open Pending Publish Recovery Plan",
                ],
                recovery_actions: [{{
                  kind: "pending_publish_recovery_plan",
                  label: "Open Pending Publish Recovery Plan",
                  route: "/api/pending-publish/recovery-plan",
                  safe_next_step: "Review backend pending-publish recovery evidence before any drain, repair, rerun, or cleanup.",
                }}],
              }}],
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
            replacementRerunPreflight,
            manualKeepRerunPreflight,
            emptyCsvFetchUrls: emptyCsvDefaultFetchUrls,
            emptyCsvLabels: emptyCsvRows.map((row) => row.targetLabel),
            emptyCsvStatusText: emptyCsvText["launch-backend-preflight-status"],
            emptyCsvRefreshInfo,
            encoderRefreshFetchUrls,
            encoderRefreshPostCalls: emptyCsvPostCalls,
            encoderRefreshInfo,
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
            capture_output=True,
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
            capture_output=True,
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

        const compactGateSource = fs.readFileSync({str(LAUNCH_COMPACT_GATE_JS)!r}, "utf8");
        const source = fs.readFileSync({str(LAUNCH_SCOPE_JS)!r}, "utf8");
        const context = {{
          window: {{}},
          document: {{ querySelectorAll() {{ return []; }} }},
        }};
        context.window.window = context.window;
        context.window.document = context.document;
        vm.createContext(context);
        vm.runInContext(compactGateSource, context);
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
            capture_output=True,
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
            capture_output=True,
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
    def test_csv_rerun_review_ui_contract_is_static_pinned(self) -> None:
        html = PAGE_QUEUE_HTML.read_text(encoding="utf-8")
        js = _launch_view_bundle()

        for snippet in (
            "rerun-review-header",
            "rerun-lifecycle-evidence",
            "rerun-review-next-action",
            "aria-live=\"polite\"",
            "rerun-preview-table",
            "<th scope=\"col\">Identity</th>",
            "<th scope=\"col\">Categories</th>",
            "Typed CSV paths can be previewed; Open CSV requires",
            "Typed CSV paths can be previewed; Open Folder requires",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, html)

        for snippet in (
            "function renderRerunReviewHeader",
            "function renderRerunLifecycleEvidence",
            "function renderRerunPreviewCategoryChips",
            "function applyRerunOpenButtonState",
            "lookup_title",
            "relative_path",
            "duplicate_source",
            "Typed CSV paths can be previewed, but Open CSV and Open Folder require",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, js)

    def test_pipeline_start_gate_ignores_local_decision_ceremony_and_keeps_active_rerun_controls(self) -> None:
        result = _run_launch_command_buttons_smoke()

        self.assertFalse(result["pipelineGate"]["blocked"])
        self.assertFalse(result["missingPreflightGate"]["blocked"])
        self.assertEqual(result["missingPreflightGate"]["state"], "stale")
        self.assertEqual(result["decisionRequestCount"], 0)
        self.assertIn("Start Pipeline", result["pipelineGate"]["reason"])
        self.assertIn("without cached Backend Preflight", result["missingPreflightGate"]["reason"])
        self.assertFalse(result["csvControl"]["pauseDisabled"])
        self.assertTrue(result["csvControl"]["rescanDisabled"])
        self.assertFalse(result["csvControl"]["stopDisabled"])
        self.assertFalse(result["csvControl"]["killDisabled"])
        self.assertIn("Pause CSV rerun after the current row/window", result["csvControl"]["pauseTitle"])
        self.assertIn("current row/window finishes", result["csvControl"]["stopTitle"])

    def test_launch_and_queue_request_collectors_keep_pipeline_scope_out_and_support_lifecycle_rerun(self) -> None:
        result = _run_launch_start_request_smoke()
        pipeline_request = result["pipelineRequest"]

        self.assertEqual(pipeline_request["mode"], "continuous")
        self.assertEqual(pipeline_request["single_file"], "C:/Source/Movie.mkv")
        self.assertEqual(pipeline_request["sleep_seconds"], 7)
        self.assertEqual(pipeline_request["schedule_override"], "run_once")
        self.assertNotIn("queue_filter", pipeline_request)
        self.assertNotIn("selected_row", pipeline_request)
        self.assertNotIn("selected_path", pipeline_request)
        self.assertFalse(result["rerunLive"]["dry_run"])
        self.assertFalse(result["rerunLive"]["plan_only"])
        self.assertEqual(result["rerunLive"]["execution_mode"], "windowed")
        self.assertEqual(result["rerunLive"]["destination_mode"], "pending_publish")
        self.assertNotIn("original_policy", result["rerunLive"])
        self.assertEqual(result["rerunLive"]["collision_policy"], "suffix")
        self.assertEqual(result["rerunLive"]["window_size"], 3)
        self.assertFalse(result["rerunLive"]["confirm_replace_final"])
        self.assertFalse(result["rerunLive"]["confirm_source_overwrite"])
        self.assertNotIn("confirm_original_policy", result["rerunLive"])
        self.assertNotIn("confirm_delete_original", result["rerunLive"])
        self.assertNotIn("original_policy", result["rerunHighRisk"])
        self.assertTrue(result["rerunHighRisk"]["confirm_replace_final"])
        self.assertTrue(result["rerunHighRisk"]["confirm_source_overwrite"])
        self.assertNotIn("confirm_original_policy", result["rerunHighRisk"])
        self.assertNotIn("confirm_delete_original", result["rerunHighRisk"])
        self.assertEqual(
            result["rerunLive"]["scope"],
            {
                "enabled_only": True,
                "skip_blocked": True,
                "skip_warning_rows": False,
                "first_n": 5,
                "issue_filters": ["audio"],
                "bucket_filters": ["movie"],
                "preview_limit": 25,
            },
        )
        self.assertNotIn("dry_run", result["rerunPreview"])
        self.assertNotIn("plan_only", result["rerunPreview"])
        self.assertEqual(result["rerunPreview"]["execution_mode"], "windowed")

    def test_backend_preflight_refresh_is_explicit_and_uses_review_start_only(self) -> None:
        result = _run_launch_preflight_smoke()

        self.assertEqual(result["renderFetchCount"], 0)
        self.assertEqual(len(result["fetchUrls"]), 1)
        self.assertFalse(any("refresh_encoder_capability_report=true" in item for item in result["fetchUrls"]))
        self.assertFalse(any("plan_only=true" in item for item in result["fetchUrls"]))
        self.assertFalse(any("dry_run=true" in item for item in result["fetchUrls"]))
        self.assertFalse(any("dry_run=false" in item for item in result["fetchUrls"]))
        self.assertEqual(sorted(set(result["labels"])), ["Pipeline"])
        self.assertEqual(result["statusText"], "Ready")
        self.assertEqual(result["statusState"], "ready")
        self.assertEqual(result["refreshInfo"]["candidate_request_count"], 1)
        self.assertEqual(result["refreshInfo"]["skipped_request_count"], 0)
        self.assertIn("Status scope: active targets only", result["stagedSummary"])
        self.assertIn("Pipeline backend preflight", result["stagedSummary"])
        self.assertIn("Encoder activation evidence: active=1 (libaom-av1); available inactive=1 (av1_nvenc); activation unknown=0.", result["stagedSummary"])
        self.assertIn("Hardware runtime proof: verified=0; skipped=1 (av1_nvenc); active unverified=1 (av1_nvenc).", result["stagedSummary"])
        self.assertIn("Active hardware encoders without runtime proof remain review-only: av1_nvenc.", result["stagedSummary"])
        self.assertIn("WebView does not enable hardware families", result["stagedSummary"])
        self.assertIn("Pairing note: final-output replacement keeps source files untouched unless source-path overwrite is explicitly confirmed.", result["replacementRerunPreflight"])
        self.assertIn("Pairing note: final-output replacement keeps source files untouched unless source-path overwrite is explicitly confirmed.", result["manualKeepRerunPreflight"])
        self.assertEqual(len(result["emptyCsvFetchUrls"]), 1)
        self.assertIn("target=pipeline", result["emptyCsvFetchUrls"][0])
        self.assertFalse(any("target=rerun" in item for item in result["emptyCsvFetchUrls"]))
        self.assertEqual(sorted(set(result["emptyCsvLabels"])), ["Pipeline"])
        self.assertEqual(result["emptyCsvStatusText"], "Ready")
        self.assertEqual(result["emptyCsvRefreshInfo"]["candidate_request_count"], 1)
        self.assertEqual(result["emptyCsvRefreshInfo"]["skipped_request_count"], 0)
        self.assertEqual(
            [item["key"] for item in result["emptyCsvRefreshInfo"]["skipped_targets"]],
            [],
        )
        self.assertEqual(result["emptyCsvRefreshInfo"]["refresh_encoder_capability_report_requested"], False)
        self.assertEqual(len(result["encoderRefreshFetchUrls"]), 1)
        self.assertIn("target=pipeline", result["encoderRefreshFetchUrls"][0])
        self.assertFalse(any("refresh_encoder_capability_report=" in item for item in result["encoderRefreshFetchUrls"]))
        self.assertEqual(
            result["encoderRefreshPostCalls"],
            [{"path": "/api/diagnostics/encoder-capabilities/refresh", "payload": {}, "timeoutMs": 65000}],
        )
        self.assertEqual(result["encoderRefreshInfo"]["refresh_encoder_capability_report_requested"], True)
        self.assertIn("Pipeline backend preflight", result["emptyCsvSummary"])
        self.assertNotIn("CSV Rerun Start", result["emptyCsvSummary"])
        self.assertIn("Encoder activation evidence: active=1 (libaom-av1); available inactive=1 (av1_nvenc); activation unknown=0.", result["emptyCsvSummary"])
        self.assertIn("Hardware runtime proof: verified=0; skipped=1 (av1_nvenc); active unverified=1 (av1_nvenc).", result["emptyCsvSummary"])
        self.assertEqual(
            {item["key"]: item["active"] for item in result["emptyCsvCandidates"]},
            {"pipeline": True},
        )
        self.assertEqual(result["poisonStatus"], "Ready")
        self.assertEqual(result["poisonRows"], ["Pipeline:ready"])
        self.assertEqual(result["poisonScopeLabel"], "Pipeline backend preflight")
        self.assertTrue(result["activeWorkAlertSuppressed"])
        self.assertIn("Pipeline launch blocked by backend preflight", result["blockedAlertText"])
        self.assertIn("What is wrong: Autonomy health gate is blocked", result["blockedAlertText"])
        self.assertIn("pipeline_version is required and cannot be blank", result["blockedAlertText"])
        self.assertIn("How to fix: Open Pending Publish", result["blockedAlertText"])
        self.assertIn("STATE_FILE_SCHEMA_REFERENCE.md", result["blockedAlertText"])
        self.assertIn("Backend detail: row_key=pending-row-1", result["blockedAlertText"])
        self.assertIn("Recovery route: Open Pending Publish Recovery Plan at /api/pending-publish/recovery-plan", result["blockedAlertText"])
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
        launch_source = _launch_view_bundle()
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
