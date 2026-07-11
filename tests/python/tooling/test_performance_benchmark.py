from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mediapipeline.core.observability.performance import (
    append_performance_records,
    performance_record,
    summarize_duration_samples,
)
from mediapipeline.tools.dev import performance_benchmark


class PerformanceBenchmarkTests(unittest.TestCase):
    def test_duration_summary_uses_nearest_rank_p95(self) -> None:
        summary = summarize_duration_samples([30, 10, 20, 40, 50])

        self.assertEqual(summary["count"], 5)
        self.assertEqual(summary["min_ms"], 10.0)
        self.assertEqual(summary["median_ms"], 30.0)
        self.assertEqual(summary["p95_ms"], 50.0)
        self.assertEqual(summary["max_ms"], 50.0)

    def test_ledger_append_is_explicit_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "performance.jsonl"
            row = performance_record(
                operation="backend_import",
                metric="median_ms",
                value=700.0,
                unit="ms",
                correct=True,
                measured_at="2026-07-10T00:00:00Z",
            )

            self.assertEqual(append_performance_records(ledger, [row]), 1)
            loaded = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(loaded["operation"], "backend_import")
            self.assertTrue(loaded["correct"])

    def test_static_shell_inventory_checks_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static_root = root / "apps" / "desktop" / "webview" / "static"
            assets = static_root / "assets"
            assets.mkdir(parents=True)
            (static_root / "index.html").write_text('<script defer src="/assets/app.js?v=1"></script>', encoding="utf-8")
            (assets / "app.js").write_text("void 0;", encoding="utf-8")

            result = performance_benchmark.benchmark_static_shell(root)

            self.assertTrue(result["correct"])
            self.assertEqual(result["external_script_count"], 1)
            self.assertEqual(result["deferred_external_script_count"], 1)
            self.assertEqual(result["external_script_bytes"], 7)

    def test_records_include_timing_and_inventory_metrics(self) -> None:
        payload = {
            "measured_at": "2026-07-10T00:00:00Z",
            "results": [
                {
                    "operation": "static_shell_inventory",
                    "correct": True,
                    "summary": {"count": 1, "min_ms": 1.0, "median_ms": 1.0, "p95_ms": 1.0, "max_ms": 1.0},
                    "external_script_count": 10,
                    "deferred_external_script_count": 10,
                    "external_script_bytes": 100,
                }
            ],
        }

        records = performance_benchmark.records_for_payload(payload, variant="candidate")

        self.assertEqual(len(records), 7)
        self.assertEqual({record["variant"] for record in records}, {"candidate"})
        self.assertEqual({record["operation"] for record in records}, {"static_shell_inventory"})


if __name__ == "__main__":
    unittest.main()
