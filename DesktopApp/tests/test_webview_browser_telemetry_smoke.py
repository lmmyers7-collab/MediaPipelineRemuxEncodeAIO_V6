from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade

ROOT = Path(__file__).resolve().parents[1]
STATIC_ASSETS = ROOT / "mediapipeline_desktop_app" / "ui_web" / "static" / "assets"

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
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            [
              "showPage",
              "renderTelemetry",
              "telemetryVisibleGpuRows",
              "telemetryReadinessLines",
              "telemetryReadinessStatus",
            ].forEach(requireFunction);

            window.showPage("live");
            window.mediaPipelineTelemetryView.renderTelemetry(payload.idleGpu);
            requireText("gpu-value", ["0%"]);
            if (text("gpu-value").includes("idle")) throw new Error("gpu-value still includes redundant idle wording");
            const zeroPercentGpuValue = text("gpu-value");
            requireText("gpu-note", ["NVENC present.", "Device: NVIDIA RTX Test", "Source: nvidia-smi"]);
            requireText("telemetry-readiness-status", ["Ready"]);
            requireText("telemetry-readiness-summary", ["GPU present: yes", "NVENC: 0%", "Telemetry is ready for operator monitoring."]);
            requireText("gpu-detail-status", ["1 GPU row"]);
            const gpuRowText = Array.from(document.querySelectorAll("#gpu-rows td")).map((cell) => cell.textContent || "").join("\\n");
            if (gpuRowText.includes("0% idle")) throw new Error("gpu detail row still includes redundant idle wording");
            for (const fragment of ["NVIDIA RTX Test", "0%", "1.0 / 8.0 GB"]) {
              if (!gpuRowText.includes(fragment)) throw new Error("gpu row missing " + fragment + "\\nActual:\\n" + gpuRowText);
            }
            const visibleRows = window.mediaPipelineTelemetryView.telemetryVisibleGpuRows(payload.idleGpu);
            if (visibleRows.length !== 1 || visibleRows[0].synthesized !== true) {
              throw new Error("top-level zero-percent GPU telemetry did not synthesize a visible GPU row");
            }

            window.mediaPipelineTelemetryView.renderTelemetry(payload.cpuOnly);
            requireText("gpu-value", ["Unavailable"]);
            requireText("gpu-note", ["NVENC telemetry unavailable; encoder graph is retained"]);
            requireText("telemetry-readiness-status", ["CPU/RAM only"]);
            requireText("gpu-detail-status", ["No GPU rows"]);
            requireText("telemetry-readiness-summary", ["GPU present: no", "GPU telemetry is unavailable"]);

            return {
              ok: true,
              zeroPercentGpuValue,
              cpuOnlyGpuValue: text("gpu-value"),
              visibleRows: visibleRows.length,
              finalReadiness: text("telemetry-readiness-status"),
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
                            "sampled_at": "2099-01-01T00:00:00Z",
                            "gpu_rows": [],
                        },
                        "cpuOnly": {
                            "cpu_percent": 22.0,
                            "memory_percent": 55.0,
                            "gpu_present": False,
                            "gpu_encoder_percent": None,
                            "gpu_name": "",
                            "source": "psutil",
                            "sampled_at": "2099-01-01T00:00:00Z",
                            "gpu_rows": [],
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

        const blankNumericPayload = {{
          cpu_percent: "",
          memory_percent: " ",
          gpu_encoder_percent: "",
          gpu_percent: "",
          gpu_name: "",
          gpu_rows: [],
          sampled_at: "2099-01-01T00:00:00Z",
        }};
        const blankStatus = view.telemetryReadinessStatus(blankNumericPayload);
        const blankLines = view.telemetryReadinessLines(blankNumericPayload);
        const blankRows = view.telemetryVisibleGpuRows(blankNumericPayload);
        const blankUsage = view.telemetryGpuUsagePayload(blankNumericPayload);
        if (blankStatus !== "Limited") throw new Error("blank numeric telemetry should be Limited, got " + blankStatus);
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
          sampled_at: "2099-01-01T00:00:00Z",
        }};
        const partialRows = view.telemetryVisibleGpuRows(partialGpuPayload);
        if (partialRows.length !== 1) throw new Error("partial GPU payload should synthesize one visible row");
        if (partialRows[0].memory_used_mb === 0 || partialRows[0].memory_total_mb === 0) {{
          throw new Error("missing GPU memory was coerced to zero");
        }}

        console.log(JSON.stringify({{
          ok: true,
          blankStatus,
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


class WebViewBrowserTelemetrySmokeTests(unittest.TestCase):
    def test_telemetry_view_treats_blank_numeric_fields_as_unavailable(self) -> None:
        result = _run_node_telemetry_view_smoke()

        self.assertTrue(result["ok"])
        self.assertEqual(result["blankStatus"], "Limited")
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
        self.assertEqual(browser_result["finalReadiness"], "CPU/RAM only")




