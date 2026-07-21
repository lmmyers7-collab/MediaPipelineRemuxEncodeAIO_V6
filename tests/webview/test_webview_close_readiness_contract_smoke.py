from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


class WebViewCloseReadinessContractSmokeTests(unittest.TestCase):
    def test_malformed_or_contradictory_close_readiness_fails_closed(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the WebView close-readiness contract smoke.")

        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const path = require("path");
            const vm = require("vm");

            const sourcePath = path.join(
              process.cwd(),
              "apps/desktop/webview/static/assets/app/closeReadiness.js",
            );
            const source = fs.readFileSync(sourcePath, "utf8");
            const context = { console };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: sourcePath });

            const closeReadiness = context.window.mediaPipelineAppCloseReadiness;
            if (!closeReadiness || typeof closeReadiness.normalizeCloseReadiness !== "function") {
              throw new Error("close-readiness semantic normalizer was not exported");
            }

            const validSafe = Object.freeze({
              schema_version: "desktop_close_readiness.v1",
              safe_to_close: true,
              active_work: false,
              state: "idle",
              reason: "No active work remains.",
              continuous_watcher: Object.freeze({
                status: "idle",
                pid: 0,
                deadline: "",
                stop_requested: false,
                generation: 0,
                message: "No backend schedule-stop watcher is armed.",
                error: "",
              }),
              warnings: Object.freeze([]),
            });
            const validBlocked = Object.freeze({
              schema_version: "desktop_close_readiness.v1",
              safe_to_close: false,
              active_work: true,
              state: "processing",
              reason: "An exact backend process is still running.",
              continuous_watcher: Object.freeze({
                status: "armed",
                pid: 4321,
                deadline: "2026-07-20T20:00:00Z",
                stop_requested: false,
                generation: 3,
                message: "Watcher remains armed.",
                error: "",
              }),
              warnings: Object.freeze(["Keep the backend alive."]),
            });

            const invalidCases = [
              ["null", null],
              ["array", []],
              ["primitive", "safe"],
              ["missing schema", { ...validSafe, schema_version: undefined }],
              ["wrong schema", { ...validSafe, schema_version: "desktop_close_readiness.v0" }],
              ["missing safe flag", { ...validSafe, safe_to_close: undefined }],
              ["string safe flag", { ...validSafe, safe_to_close: "true" }],
              ["missing active-work flag", { ...validSafe, active_work: undefined }],
              ["string active-work flag", { ...validSafe, active_work: "false" }],
              ["missing state", { ...validSafe, state: undefined }],
              ["empty state", { ...validSafe, state: "" }],
              ["non-string state", { ...validSafe, state: 7 }],
              ["missing reason", { ...validSafe, reason: undefined }],
              ["empty reason", { ...validSafe, reason: "   " }],
              ["non-string reason", { ...validSafe, reason: { text: "idle" } }],
              ["warnings object", { ...validSafe, warnings: {} }],
              ["warnings with non-string", { ...validSafe, warnings: ["one", 2] }],
              ["watcher array", { ...validSafe, continuous_watcher: [] }],
              ["watcher primitive", { ...validSafe, continuous_watcher: "idle" }],
              ["safe while active", { ...validSafe, active_work: true }],
              ["blocked while inactive", { ...validBlocked, active_work: false }],
              ["safe processing state", { ...validSafe, state: "processing" }],
              ["safe unknown state", { ...validSafe, state: "unknown" }],
              [
                "safe with armed watcher",
                { ...validSafe, continuous_watcher: { ...validSafe.continuous_watcher, status: "armed", pid: 4321 } },
              ],
              [
                "safe with watcher error",
                { ...validSafe, continuous_watcher: { ...validSafe.continuous_watcher, status: "error", error: "unverified" } },
              ],
            ];

            const failures = [];
            function check(condition, message) {
              if (!condition) failures.push(message);
            }

            const normalizedSafe = closeReadiness.normalizeCloseReadiness(validSafe);
            check(normalizedSafe.safe_to_close === true, "valid fresh safe evidence was not usable");
            check(normalizedSafe.active_work === false, "valid fresh safe evidence was changed to active");
            check(normalizedSafe.state === "idle", "valid fresh safe state was not preserved");
            check(
              normalizedSafe.evidence_authority !== "frontend-fail-closed-sentinel",
              "valid fresh safe evidence was replaced by an unavailable sentinel",
            );
            check(
              closeReadiness.closeReadinessRequiresWarning(normalizedSafe, { pipeline_state: "idle" }) === false,
              "valid fresh safe evidence incorrectly requires a close warning",
            );

            const normalizedBlocked = closeReadiness.normalizeCloseReadiness(validBlocked);
            check(normalizedBlocked.safe_to_close === false, "valid blocked evidence was made safe");
            check(normalizedBlocked.active_work === true, "valid blocked evidence lost active-work truth");
            check(
              closeReadiness.closeReadinessRequiresWarning(normalizedBlocked, { pipeline_state: "processing" }) === true,
              "valid blocked evidence does not require a close warning",
            );

            for (const [label, payload] of invalidCases) {
              const unavailableReason = `Malformed close-readiness (${label}).`;
              const normalized = closeReadiness.normalizeCloseReadiness(payload, unavailableReason);
              check(normalized && typeof normalized === "object", `${label}: normalizer returned no fail-closed object`);
              check(normalized.safe_to_close === false, `${label}: malformed evidence remained safe to close`);
              check(normalized.active_work === true, `${label}: malformed evidence did not conservatively report active work`);
              check(normalized.state === "unavailable", `${label}: malformed evidence was presented as state=${normalized.state}`);
              check(normalized.operator_status === "unavailable", `${label}: malformed evidence lacked unavailable operator status`);
              check(
                normalized.evidence_authority === "frontend-fail-closed-sentinel",
                `${label}: malformed evidence retained apparent backend authority`,
              );
              check(normalized.reason === unavailableReason, `${label}: fail-closed reason was not deterministic`);
              check(
                Array.isArray(normalized.warnings) && normalized.warnings.length === 1 && normalized.warnings[0] === unavailableReason,
                `${label}: fail-closed warning evidence was not deterministic`,
              );
              check(
                closeReadiness.closeReadinessRequiresWarning(normalized, { pipeline_state: "idle" }) === true,
                `${label}: unavailable evidence did not require a close warning`,
              );
            }

            check(validSafe.safe_to_close === true, "normalization mutated the frozen safe fixture");
            check(validBlocked.safe_to_close === false, "normalization mutated the frozen blocked fixture");
            if (failures.length) {
              throw new Error(`Close-readiness contract failures:\n- ${failures.join("\n- ")}`);
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
