from __future__ import annotations

import unittest

from mediapipeline.tools.dev.code_context_benchmark import acceptance_findings, load_cases


class CodeContextBenchmarkTests(unittest.TestCase):
    def test_versioned_fixture_has_48_unique_complete_cases(self) -> None:
        cases = load_cases()
        self.assertEqual(len(cases), 48)
        self.assertEqual(len({case["id"] for case in cases}), 48)
        self.assertTrue(all(case["authority_paths"] for case in cases))
        self.assertTrue(all(case["required_layers"] for case in cases))
        self.assertTrue(all(case["expected_test_paths"] for case in cases))
        self.assertTrue(all(case["boundary_paths"] for case in cases if case["high_risk"]))

    def test_acceptance_thresholds_are_release_gates(self) -> None:
        passing = {
            "quality": {
                "authority_recall_at_5": 0.90,
                "authority_recall_at_10": 0.97,
                "vertical_slice_completeness": 0.80,
                "irrelevant_top_10_rate": 0.20,
                "high_risk_test_coverage": 1.0,
                "high_risk_boundary_coverage": 1.0,
            },
            "latency_ms": {"repo_context_p95": 50, "code_search_p95": 300, "index_reload": 250},
        }
        self.assertEqual(acceptance_findings(passing), [])
        passing["quality"]["authority_recall_at_5"] = 0.89
        passing["latency_ms"]["code_search_p95"] = 301
        findings = acceptance_findings(passing)
        self.assertIn("authority Recall@5 is below 90%", findings)
        self.assertIn("code_search p95 exceeds 300 ms", findings)


if __name__ == "__main__":
    unittest.main()
