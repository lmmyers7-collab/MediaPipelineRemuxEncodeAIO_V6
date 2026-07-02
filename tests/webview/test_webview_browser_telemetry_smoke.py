from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timedelta, timezone, UTC
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

ROOT = find_repo_root(Path(__file__))
STATIC_ASSETS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets"

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


def _browser_telemetry_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function telemetryScript(data) {
          return `
          (() => {
            const payload = ${JSON.stringify(data)};
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function resolveCssColor(token) {
              const probe = document.createElement("span");
              probe.style.color = "var(" + token + ")";
              document.body.appendChild(probe);
              const color = getComputedStyle(probe).color;
              probe.remove();
              return color;
            }
            function requireNotColor(selector, property, blockedToken) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing selector " + selector);
              const actual = getComputedStyle(node)[property];
              const blocked = resolveCssColor(blockedToken);
              if (actual === blocked) {
                throw new Error(selector + " " + property + " unexpectedly used " + blockedToken + " (" + actual + ")");
              }
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireGpuDetailsSimplifiedTableControls() {
              window.mediaPipelineDom?.enhanceDataTables?.();
              const table = byId("gpu-rows")?.closest("table");
              if (!table) throw new Error("missing GPU Details table");
              const toolbar = document.querySelector('[data-table-toolbar-for="' + table.id + '"]');
              if (!toolbar) throw new Error("missing GPU Details table toolbar");
              if (!toolbar.querySelector(".table-column-menu")) throw new Error("GPU Details table lost the retained Columns menu");
              for (const selector of [".table-ui-filter", ".table-density-control", ".table-column-filter-toggle"]) {
                if (toolbar.querySelector(selector)) throw new Error("GPU Details toolbar retained removed control " + selector);
              }
              for (const selector of [".table-filter-row", ".table-column-filter"]) {
                if (table.querySelector(selector)) throw new Error("GPU Details table retained removed filter-row control " + selector);
              }
              for (const fragment of ["Filter rows", "Column filters", "Compact", "Comfortable"]) {
                if (toolbar.textContent.includes(fragment)) throw new Error("GPU Details toolbar retained removed text " + fragment);
              }
            }
            async function assertTelemetryViewport(width, height) {
              void height;
              await new Promise((resolve) => setTimeout(resolve, 120));
              const pageOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
              if (pageOverflow > 2) {
                throw new Error("page-level horizontal overflow at " + width + "px: " + pageOverflow);
              }
              const wrap = document.querySelector(".detail-table-wrap");
              const table = document.querySelector(".detail-table-wrap table");
              if (!wrap || !table) throw new Error("missing telemetry GPU detail table wrap");
              if (table.scrollWidth > wrap.clientWidth + 2 && getComputedStyle(wrap).overflowX === "visible") {
                throw new Error("GPU Details overflow was not contained at " + width + "px");
              }
            }
            function requireTelemetryFunction(name) {
              if (typeof window.mediaPipelineTelemetryView?.[name] !== "function") {
                throw new Error("missing telemetry namespace function " + name);
              }
            }
            if (typeof window.showPage !== "function") throw new Error("missing global function showPage");
            [
              "renderTelemetry",
              "telemetryVisibleGpuRows",
              "telemetryReadinessLines",
              "telemetryReadinessStatus",
            ].forEach(requireTelemetryFunction);
            if (typeof window.mediaPipelineTelemetryView.telemetryOperatingState !== "function") {
              throw new Error("missing telemetryOperatingState namespace export");
            }
            if (typeof window.mediaPipelineTelemetryView.telemetryChartMetaText !== "function") {
              throw new Error("missing telemetryChartMetaText namespace export");
            }
            if (typeof window.mediaPipelineTelemetryView.redrawTelemetryCharts !== "function") {
              throw new Error("missing redrawTelemetryCharts namespace export");
            }
            if (typeof window.mediaPipelineTelemetryView.telemetryHistorySnapshot !== "function") {
              throw new Error("missing telemetryHistorySnapshot namespace export");
            }

            window.showPage("live");
            window.mediaPipelineTelemetryView.renderTelemetry(payload.idleGpu, { refreshIntervalMs: 15000 });
            requireText("gpu-value", ["0%"]);
            if (text("gpu-value").includes("idle")) throw new Error("gpu-value still includes redundant idle wording");
            const zeroPercentGpuValue = text("gpu-value");
            requireText("gpu-note", ["GPU video encoder is idle at 0%.", "Device: NVIDIA RTX Test", "Source: nvidia-smi"]);
            requireText("telemetry-readiness-status", ["Idle"]);
            requireText("telemetry-operator-state-label", ["Idle"]);
            requireText("telemetry-operator-next-step", ["No active work is reported; hardware usage looks idle."]);
            requireText("telemetry-readiness-summary", ["Operating state: Idle", "GPU present: yes", "Video encoder (NVENC): 0%"]);
            requireText("cpu-chart-meta", ["0-100%", "Last ~8 min", "UI refresh 15s", "GPU probe up to 12s", "Sample age"]);
            requireText("telemetry-live-state", ["Idle"]);
            requireText("telemetry-sample-age", ["s"]);
            requireText("telemetry-source", ["nvidia-smi"]);
            requireText("telemetry-expected-encoder", ["No active work"]);
            requireText("telemetry-refresh-cadence", ["UI 15s", "GPU 12s"]);
            requireText("telemetry-kpi-cpu-value", ["13%"]);
            requireText("telemetry-kpi-encoder-value", ["0%"]);
            requireText("telemetry-kpi-ram-value", ["41%"]);
            requireText("telemetry-kpi-gpu-status", ["Available"]);
            if (byId("telemetry-kpi-encoder-value").dataset.state !== "idle") throw new Error("0% NVENC was not marked idle");
            requireNotColor('[data-telemetry-kpi="cpu"]', "borderLeftColor", "--semantic-success-accent");
            requireNotColor('[data-telemetry-kpi="ram"]', "borderLeftColor", "--semantic-success-accent");
            requireNotColor('[data-telemetry-kpi="gpu"]', "borderLeftColor", "--semantic-success-accent");
            requireNotColor('[data-telemetry-chart-panel="cpu"]', "borderLeftColor", "--semantic-success-accent");
            requireNotColor('[data-telemetry-chart-panel="ram"]', "borderLeftColor", "--semantic-success-accent");
            requireNotColor("#telemetry-kpi-cpu-value", "color", "--semantic-success-text");
            requireText("gpu-detail-status", ["1 GPU row"]);
            const gpuRowText = Array.from(document.querySelectorAll("#gpu-rows td")).map((cell) => cell.textContent || "").join("\\n");
            if (gpuRowText.includes("0% idle")) throw new Error("gpu detail row still includes redundant idle wording");
            for (const fragment of ["NVIDIA RTX Test", "Idle", "0%", "1.0 / 8.0 GB"]) {
              if (!gpuRowText.includes(fragment)) throw new Error("gpu row missing " + fragment + "\\nActual:\\n" + gpuRowText);
            }
            requireGpuDetailsSimplifiedTableControls();
            const visibleRows = window.mediaPipelineTelemetryView.telemetryVisibleGpuRows(payload.idleGpu);
            if (visibleRows.length !== 1 || visibleRows[0].synthesized !== true) {
              throw new Error("top-level zero-percent GPU telemetry did not synthesize a visible GPU row");
            }

            window.mediaPipelineTelemetryView.renderTelemetry(payload.structuredGpu, { refreshIntervalMs: 15000 });
            const structuredRowText = Array.from(document.querySelectorAll("#gpu-rows td")).map((cell) => cell.textContent || "").join("\\n");
            for (const fragment of ["Read warning", "2", "not reported", "72 C", "unit-fixture | warning: sensor read failed"]) {
              if (!structuredRowText.includes(fragment)) throw new Error("structured GPU row missing " + fragment + "\\nActual:\\n" + structuredRowText);
            }
            requireText("telemetry-readiness-status", ["Telemetry source warning"]);
            requireText("telemetry-operator-next-step", ["Telemetry source is not fully trusted", "fixture-like", "sensor read failed"]);
            requireText("telemetry-source", ["gpu-contract", "row unit-fixture"]);
            requireText("telemetry-readiness-summary", ["Contract: desktop_gpu_encoder_usage.v1", "Encoder sessions: 2 active", "Source warning:"]);
            requireText("telemetry-kpi-gpu-status", ["Warning"]);

            window.mediaPipelineTelemetryView.renderTelemetry(payload.structuredGpuMissingRowSource, { refreshIntervalMs: 15000 });
            const inheritedSourceRowText = Array.from(document.querySelectorAll("#gpu-rows td")).map((cell) => cell.textContent || "").join("\\n");
            if (!inheritedSourceRowText.includes("gpu-contract")) {
              throw new Error("structured GPU row did not inherit payload/top-level source\\nActual:\\n" + inheritedSourceRowText);
            }

            window.mediaPipelineTelemetryView.renderTelemetry(payload.activeGpu, { snapshot: payload.activeSnapshot, refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["GPU-bound encode"]);
            requireText("telemetry-operator-next-step", ["GPU video encoder is the likely bottleneck"]);
            if (document.querySelector('[data-telemetry-chart-panel="encoder"]').dataset.state !== "active") {
              throw new Error("active NVENC chart panel was not marked active");
            }

            window.mediaPipelineTelemetryView.renderTelemetry(payload.expectedIdle, { snapshot: payload.activeSnapshot, refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["NVENC expected but idle"]);
            requireText("telemetry-operator-next-step", ["hardware encode"]);
            if (byId("telemetry-kpi-encoder-value").dataset.state !== "warning") throw new Error("expected idle NVENC was not marked warning");

            window.mediaPipelineTelemetryView.renderTelemetry(payload.remuxIdle, { snapshot: payload.remuxSnapshot, refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["NVENC idle as expected"]);
            requireText("telemetry-operator-next-step", ["does not appear to require NVENC"]);

            window.mediaPipelineTelemetryView.renderTelemetry(payload.cpuBound, { snapshot: payload.activeSnapshot, refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["CPU-bound encode"]);
            requireText("telemetry-operator-next-step", ["CPU is likely limiting the current job"]);

            window.mediaPipelineTelemetryView.renderTelemetry(payload.memoryPressure, { snapshot: payload.activeSnapshot, refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["NVENC expected but idle"]);
            requireText("telemetry-operator-next-step", ["NVENC is 0%", "RAM pressure is also high"]);

            window.mediaPipelineTelemetryView.renderTelemetry(payload.memoryPressureOnly, { snapshot: payload.activeSnapshot, refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["Memory pressure"]);
            requireText("telemetry-operator-next-step", ["RAM pressure is high"]);

            window.mediaPipelineTelemetryView.renderTelemetry(payload.cpuOnly, { refreshIntervalMs: 15000 });
            requireText("gpu-value", ["Unavailable"]);
            requireText("gpu-note", ["GPU video encoder telemetry unavailable. CPU/RAM data is still usable."]);
            requireText("telemetry-readiness-status", ["CPU/RAM only"]);
            requireText("gpu-detail-status", ["No GPU rows"]);
            requireText("telemetry-readiness-summary", ["GPU present: no", "GPU video encoder telemetry is not available"]);
            requireText("telemetry-kpi-gpu-status", ["Not available"]);
            const cpuOnlyGpuValue = text("gpu-value");
            const historyAfterCpuOnly = window.mediaPipelineTelemetryView.telemetryHistorySnapshot();
            if (historyAfterCpuOnly.gpu[historyAfterCpuOnly.gpu.length - 1] !== null) {
              throw new Error("missing GPU telemetry did not create a chart gap");
            }

            window.mediaPipelineTelemetryView.renderTelemetry(payload.warning, { refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["Telemetry degraded"]);
            requireText("telemetry-operator-next-step", ["If hardware encoding is expected, inspect Maintenance GPU tools, Diagnostics nvidia-smi, and Video settings."]);

            window.mediaPipelineTelemetryView.renderTelemetry(null, { refreshIntervalMs: 15000, unavailableReason: "request timed out" });
            requireText("telemetry-readiness-status", ["Telemetry unavailable"]);
            requireText("telemetry-readiness-summary", ["Payload: unavailable", "request timed out"]);
            requireText("telemetry-kpi-gpu-status", ["Unavailable"]);
            const historyAfterUnavailable = window.mediaPipelineTelemetryView.telemetryHistorySnapshot();
            if (historyAfterUnavailable.cpu[historyAfterUnavailable.cpu.length - 1] !== null) {
              throw new Error("unavailable telemetry did not create a CPU chart gap");
            }

            window.mediaPipelineTelemetryView.renderTelemetry(payload.future, { refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["Telemetry clock skew"]);
            requireText("telemetry-kpi-gpu-status", ["Clock skew"]);

            window.mediaPipelineTelemetryView.renderTelemetry(payload.stale, { refreshIntervalMs: 15000 });
            requireText("telemetry-readiness-status", ["Telemetry stale"]);
            requireText("telemetry-operator-next-step", ["backend sampler"]);
            requireText("telemetry-kpi-gpu-status", ["Stale"]);

            window.mediaPipelineTelemetryView.renderTelemetry(payload.activeGpu, { snapshot: payload.activeSnapshot, refreshIntervalMs: 15000 });
            const beforeThemeRedraw = byId("cpu-chart").toDataURL();
            document.body.classList.add("light-mode");
            window.mediaPipelineTelemetryView.redrawTelemetryCharts();
            const afterThemeRedraw = byId("cpu-chart").toDataURL();
            if (beforeThemeRedraw === afterThemeRedraw) throw new Error("theme redraw did not update telemetry canvas pixels");
            document.body.classList.remove("light-mode");
            window.mediaPipelineTelemetryView.redrawTelemetryCharts();
            window.__assertTelemetryViewport = assertTelemetryViewport;

            return {
              ok: true,
              zeroPercentGpuValue,
              cpuOnlyGpuValue,
              visibleRows: visibleRows.length,
              finalReadiness: text("telemetry-readiness-status"),
              activeState: window.mediaPipelineTelemetryView.telemetryOperatingState(payload.activeGpu, { snapshot: payload.activeSnapshot }).label,
              chartMeta: text("cpu-chart-meta"),
              encoderState: byId("telemetry-kpi-encoder-value").dataset.state,
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
                expression: `Boolean(document.getElementById("gpu-chart") && document.getElementById("gpu-rows") && typeof window.showPage === "function" && typeof window.mediaPipelineTelemetryView.renderTelemetry === "function" && typeof window.mediaPipelineTelemetryView.telemetryVisibleGpuRows === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("gpu-chart") && document.getElementById("gpu-rows") && typeof window.showPage === "function" && typeof window.mediaPipelineTelemetryView.renderTelemetry === "function" && typeof window.mediaPipelineTelemetryView.telemetryVisibleGpuRows === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Telemetry WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: telemetryScript(payload.telemetryPayload),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            for (const viewport of [
              { width: 390, height: 900, mobile: true },
              { width: 768, height: 900, mobile: false },
              { width: 1440, height: 1000, mobile: false },
            ]) {
              await client.send("Emulation.setDeviceMetricsOverride", {
                width: viewport.width,
                height: viewport.height,
                deviceScaleFactor: 1,
                mobile: viewport.mobile,
              });
              const viewportResult = await client.send("Runtime.evaluate", {
                expression: `window.__assertTelemetryViewport(${viewport.width}, ${viewport.height})`,
                awaitPromise: true,
                returnByValue: true,
              });
              if (viewportResult.exceptionDetails) {
                const details = viewportResult.exceptionDetails;
                throw new Error(details.exception?.description || details.exception?.value || details.text || "telemetry viewport evaluation failed");
              }
            }
            await client.send("Emulation.clearDeviceMetricsOverride");
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


def _run_browser_telemetry_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView telemetry smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-telemetry-payload.json"
        runner_path = tmp / "browser-telemetry-runner.cjs"
        now = datetime.now(UTC)
        fresh_sample = now.isoformat().replace("+00:00", "Z")
        future_sample = (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "telemetryPayload": {
                        "idleGpu": {
                            "cpu_percent": 12.5,
                            "memory_percent": 41.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 0.0,
                            "gpu_percent": 0.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "gpu_index": "0",
                            "gpu_memory_used_gb": 1.0,
                            "gpu_memory_total_gb": 8.0,
                            "source": "nvidia-smi",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                        },
                        "structuredGpu": {
                            "cpu_percent": 31.0,
                            "memory_percent": 50.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 12.0,
                            "gpu_percent": 24.0,
                            "gpu_name": "NVIDIA RTX Structured",
                            "source": "gpu-contract",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                            "gpu_encoder_usage": {
                                "schema_version": "desktop_gpu_encoder_usage.v1",
                                "status": "warning",
                                "row_count": 1,
                                "active_encoder_count": 1,
                                "missing_session_count": 0,
                                "read_only": True,
                                "summary_lines": ["Encoder sessions: 2 active"],
                                "rows": [
                                    {
                                        "adapter_index": "0",
                                        "adapter": "NVIDIA RTX Structured",
                                        "utilization_percent": 12.0,
                                        "gpu_utilization_percent": 24.0,
                                        "memory_used_mb": None,
                                        "memory_total_mb": None,
                                        "temperature_c": 72,
                                        "encoder_sessions": 2,
                                        "source": "unit-fixture",
                                        "read_error": "sensor read failed",
                                    }
                                ],
                            },
                        },
                        "structuredGpuMissingRowSource": {
                            "cpu_percent": 28.0,
                            "memory_percent": 48.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 18.0,
                            "gpu_percent": 30.0,
                            "gpu_name": "NVIDIA RTX Structured",
                            "source": "gpu-contract",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                            "gpu_encoder_usage": {
                                "schema_version": "desktop_gpu_encoder_usage.v1",
                                "status": "loaded",
                                "source": "gpu-contract",
                                "row_count": 1,
                                "active_encoder_count": 1,
                                "missing_session_count": 0,
                                "read_only": True,
                                "summary_lines": ["Encoder sessions: 1 active"],
                                "rows": [
                                    {
                                        "adapter_index": "0",
                                        "adapter": "NVIDIA RTX Structured",
                                        "utilization_percent": 18.0,
                                        "gpu_utilization_percent": 30.0,
                                        "memory_used_mb": 2048,
                                        "memory_total_mb": 8192,
                                        "temperature_c": 66,
                                        "encoder_sessions": 1,
                                    }
                                ],
                            },
                        },
                        "activeGpu": {
                            "cpu_percent": 37.0,
                            "memory_percent": 64.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 91.0,
                            "gpu_percent": 82.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "gpu_index": "0",
                            "gpu_memory_used_gb": 6.5,
                            "gpu_memory_total_gb": 12.0,
                            "source": "nvidia-smi",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [
                                {
                                    "index": "0",
                                    "name": "NVIDIA RTX Test",
                                    "encoder_percent": 91.0,
                                    "gpu_percent": 82.0,
                                    "memory_used_mb": 6656,
                                    "memory_total_mb": 12288,
                                }
                            ],
                        },
                        "expectedIdle": {
                            "cpu_percent": 37.0,
                            "memory_percent": 64.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 0.0,
                            "gpu_percent": 4.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "gpu_index": "0",
                            "source": "nvidia-smi",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                        },
                        "remuxIdle": {
                            "cpu_percent": 18.0,
                            "memory_percent": 42.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 0.0,
                            "gpu_percent": 2.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "gpu_index": "0",
                            "source": "nvidia-smi",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                        },
                        "cpuBound": {
                            "cpu_percent": 96.0,
                            "memory_percent": 45.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 4.0,
                            "gpu_percent": 6.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "gpu_index": "0",
                            "source": "nvidia-smi",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                        },
                        "memoryPressure": {
                            "cpu_percent": 44.0,
                            "memory_percent": 91.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 0.0,
                            "gpu_percent": 2.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "gpu_index": "0",
                            "source": "nvidia-smi",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                        },
                        "memoryPressureOnly": {
                            "cpu_percent": 44.0,
                            "memory_percent": 91.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 32.0,
                            "gpu_percent": 36.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "gpu_index": "0",
                            "source": "nvidia-smi",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                        },
                        "cpuOnly": {
                            "cpu_percent": 22.0,
                            "memory_percent": 55.0,
                            "gpu_present": False,
                            "gpu_encoder_percent": None,
                            "gpu_name": "",
                            "source": "psutil",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                        },
                        "warning": {
                            "cpu_percent": 30.0,
                            "memory_percent": 50.0,
                            "gpu_present": False,
                            "gpu_encoder_percent": None,
                            "gpu_name": "",
                            "source": "psutil",
                            "error": "nvidia-smi not found; GPU encoder telemetry unavailable.",
                            "sampled_at": fresh_sample,
                            "gpu_rows": [],
                        },
                        "future": {
                            "cpu_percent": 25.0,
                            "memory_percent": 49.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 12.0,
                            "gpu_percent": 20.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "source": "nvidia-smi",
                            "sampled_at": future_sample,
                            "gpu_rows": [],
                        },
                        "stale": {
                            "cpu_percent": 25.0,
                            "memory_percent": 49.0,
                            "gpu_present": True,
                            "gpu_encoder_percent": 12.0,
                            "gpu_percent": 20.0,
                            "gpu_name": "NVIDIA RTX Test",
                            "source": "nvidia-smi",
                            "sampled_at": "2000-01-01T00:00:00Z",
                            "gpu_rows": [],
                        },
                        "activeSnapshot": {
                            "pipeline_state": "processing",
                            "current_work": {
                                "item_label": "Example encode"
                            },
                        },
                        "remuxSnapshot": {
                            "pipeline_state": "processing",
                            "current_work": {
                                "item_label": "Example remux",
                                "route_label": "remux copy"
                            },
                        },
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_telemetry_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView telemetry smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


def _run_node_telemetry_view_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the WebView telemetry view smoke.")

    formatters_path = STATIC_ASSETS / "formatters.js"
    telemetry_path = STATIC_ASSETS / "telemetryView.js"
    formatters_source = json.dumps(formatters_path.read_text(encoding="utf-8"))
    telemetry_source = json.dumps(telemetry_path.read_text(encoding="utf-8"))
    script = textwrap.dedent(
        f"""
        const vm = require("vm");
        const formattersSource = {formatters_source};
        const telemetrySource = {telemetry_source};

        const context = {{}};
        context.window = context;
        context.document = {{
          body: {{ classList: {{ contains() {{ return false; }} }} }},
          documentElement: {{}},
        }};
        vm.createContext(context);
        vm.runInContext(formattersSource, context, {{ filename: "formatters.js" }});
        vm.runInContext(telemetrySource, context, {{ filename: "telemetryView.js" }});

        const view = context.mediaPipelineTelemetryView;
        if (!view) throw new Error("telemetry namespace was not created");
        const freshSample = new Date().toISOString();

        const blankNumericPayload = {{
          cpu_percent: "",
          memory_percent: " ",
          gpu_encoder_percent: "",
          gpu_percent: "",
          gpu_name: "",
          gpu_rows: [],
          sampled_at: freshSample,
        }};
        const blankStatus = view.telemetryReadinessStatus(blankNumericPayload);
        const blankOperatingState = view.telemetryOperatingState(blankNumericPayload);
        const blankLines = view.telemetryReadinessLines(blankNumericPayload);
        const blankRows = view.telemetryVisibleGpuRows(blankNumericPayload);
        const blankUsage = view.telemetryGpuUsagePayload(blankNumericPayload);
        if (blankStatus !== "Waiting for telemetry") throw new Error("blank numeric telemetry should be Waiting for telemetry, got " + blankStatus);
        if (blankOperatingState.key !== "waiting") throw new Error("blank numeric telemetry should use waiting state");
        if (!blankLines.includes("Operating state: Waiting for telemetry")) throw new Error("blank telemetry did not expose waiting state");
        if (!blankLines.includes("CPU: unavailable")) throw new Error("blank CPU rendered as available: " + blankLines.join("\\n"));
        if (!blankLines.includes("RAM: unavailable")) throw new Error("blank RAM rendered as available: " + blankLines.join("\\n"));
        if (!blankLines.includes("GPU present: no")) throw new Error("blank GPU rendered as present: " + blankLines.join("\\n"));
        if (blankRows.length !== 0) throw new Error("blank numeric GPU payload synthesized rows");
        if (blankUsage.status !== "unavailable") throw new Error("blank usage status should be unavailable");

        const partialGpuPayload = {{
          gpu_encoder_percent: 0,
          gpu_percent: 0,
          gpu_name: "NVIDIA Partial",
          gpu_index: "0",
          gpu_memory_used_gb: null,
          gpu_memory_total_gb: null,
          gpu_rows: [],
          sampled_at: freshSample,
        }};
        const partialRows = view.telemetryVisibleGpuRows(partialGpuPayload);
        if (partialRows.length !== 1) throw new Error("partial GPU payload should synthesize one visible row");
        if (partialRows[0].memory_used_mb === 0 || partialRows[0].memory_total_mb === 0) {{
          throw new Error("missing GPU memory was coerced to zero");
        }}

        console.log(JSON.stringify({{
          ok: true,
          blankStatus,
          blankOperatingState: blankOperatingState.key,
          blankRows: blankRows.length,
          blankUsageStatus: blankUsage.status,
          partialRows: partialRows.length,
          partialMemoryUsed: partialRows[0].memory_used_mb ?? null,
          partialMemoryTotal: partialRows[0].memory_total_mb ?? null,
        }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "telemetry-view-smoke.cjs"
        payload_path = Path(raw_tmp) / "telemetry-view-payload.json"
        payload_path.write_text("{}", encoding="utf-8")
        runner.write_text(script, encoding="utf-8")
        return run_node_browser_smoke(
            "WebView telemetry view smoke",
            node=node,
            runner_path=runner,
            payload_path=payload_path,
            timeout_seconds=20,
        )


class WebViewBrowserTelemetrySmoke(unittest.TestCase):
    def test_telemetry_view_treats_blank_numeric_fields_as_unavailable(self) -> None:
        result = _run_node_telemetry_view_smoke()

        self.assertTrue(result["ok"])
        self.assertEqual(result["blankStatus"], "Waiting for telemetry")
        self.assertEqual(result["blankOperatingState"], "waiting")
        self.assertEqual(result["blankRows"], 0)
        self.assertEqual(result["blankUsageStatus"], "unavailable")
        self.assertEqual(result["partialRows"], 1)
        self.assertIsNone(result["partialMemoryUsed"])
        self.assertIsNone(result["partialMemoryTotal"])

    def test_real_browser_keeps_zero_percent_nvenc_visible(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView telemetry smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-telemetry-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_telemetry_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["visibleRows"], 1)
        self.assertEqual(browser_result["cpuOnlyGpuValue"], "Unavailable")
        self.assertEqual(browser_result["finalReadiness"], "GPU-bound encode")
        self.assertEqual(browser_result["activeState"], "GPU-bound encode")
        self.assertIn("Last ~8 min", browser_result["chartMeta"])
