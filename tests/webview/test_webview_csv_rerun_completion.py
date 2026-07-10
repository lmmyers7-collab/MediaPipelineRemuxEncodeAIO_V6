from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


class WebViewCsvRerunCompletionTests(unittest.TestCase):
    def test_backend_completion_summary_suppresses_stale_current_progress(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the WebView CSV completion smoke.")
        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const progressPath = path.join(process.cwd(), "apps/desktop/webview/static/assets/progressView.js");
            const source = fs.readFileSync(progressPath, "utf8");
            const rendered = {};
            const context = {
              window: {}, console, Date,
              setText(id, value) { rendered[id] = String(value); }, byId() { return null; },
              mediaPipelineFormatters: { formatProgressValue(value) { return value == null ? "" : String(value); } },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: progressPath });
            const progress = context.window.mediaPipelineProgressView;
            if (typeof progress.csvRerunCompletionSummary !== "function") {
              throw new Error("missing backend CSV rerun completion summary reader");
            }
            const snapshot = {
              activity: "Stale progress from previous run; latest event: tool_started.",
              pipeline_state: "stale",
              csv_rerun_summary: {
                schema_version: "desktop_csv_rerun_completion.v1",
                evidence_authority: "backend_manifest",
                terminal: true,
                display_label: "CSV rerun complete",
                display_state: "ok",
                csv_name: "current-rerun.csv",
                detail: "current-rerun.csv · 3 processed · 3 completed · 0 failed · 0 skipped · 0 held · 0 pending · 0 pending publish",
                totals: { total: 3, processed: 3, completed: 3, failed: 0, skipped: 0, held: 0, pending: 0, pending_publish: 0 },
              },
              progress: { CurrentStage: "csv_rerun" },
            };
            const completion = progress.csvRerunCompletionSummary(snapshot);
            if (!completion || completion.csv_name !== "current-rerun.csv") {
              throw new Error(`backend completion summary was not accepted: ${JSON.stringify(completion)}`);
            }
            const status = progress.liveRunStatus({ snapshot, closeReadiness: { safe_to_close: true } });
            if (status.label !== "CSV rerun complete" || status.state !== "ok") {
              throw new Error(`stale progress overrode backend completion state: ${JSON.stringify(status)}`);
            }
            const items = progress.liveRunStripItems({ snapshot, closeReadiness: { safe_to_close: true } });
            if (items[0]?.value !== "CSV rerun complete" || items.some((item) => item.value === "Stale progress" || /Route decision pending/.test(item.value))) {
              throw new Error(`completion strip retained fake current progress: ${JSON.stringify(items)}`);
            }
            const timeline = progress.runTimelineItems({ snapshot });
            if (timeline.length !== 1 || timeline[0].label !== "CSV rerun complete" || timeline[0].status !== "complete" || timeline[0].current) {
              throw new Error(`completion timeline was not terminal: ${JSON.stringify(timeline)}`);
            }
            progress.renderHomeActiveWork({ snapshot, closeReadiness: { safe_to_close: true } });
            if (!rendered["home-active-work-summary"]?.includes("CSV rerun: CSV rerun complete") || /Stale progress|Route decision pending/.test(rendered["home-active-work-summary"])) {
              throw new Error(`Home active-work card did not suppress stale current progress: ${rendered["home-active-work-summary"]}`);
            }
            """
        )
        result = subprocess.run([node, "-e", script], cwd=repo_root, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
