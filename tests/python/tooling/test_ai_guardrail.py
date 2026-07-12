from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
MODULE_PATH = REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "ai_guardrail.py"
spec = importlib.util.spec_from_file_location("ai_guardrail_for_tests", MODULE_PATH)
assert spec and spec.loader
ai_guardrail = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ai_guardrail
spec.loader.exec_module(ai_guardrail)


class AiGuardrailTests(unittest.TestCase):
    def test_preflight_and_postflight_include_core_guardrail_checks(self) -> None:
        for mode in ("preflight", "postflight"):
            with self.subTest(mode=mode):
                names = {check.name for check in ai_guardrail.build_check_plan(mode)}

                self.assertIn("summary-freshness", names)
                self.assertIn("project-index", names)
                self.assertIn("pipeline-map", names)
                self.assertIn("lifecycle-map", names)
                self.assertIn("dependency-boundaries", names)
                self.assertIn("architecture-guardrails", names)
                self.assertIn("naming-lint", names)
                self.assertIn("god-file-guard", names)
                self.assertIn("risky-file-registry", names)

    def test_status_parser_includes_rename_destination_and_untracked_paths(self) -> None:
        sample = "\n".join(
            [
                " M src/mediapipeline/tools/dev/refresh_summaries.py",
                "?? src/mediapipeline/tools/dev/ai_guardrail.py",
                "R  old/path.py -> src/mediapipeline/contracts/lifecycle.py",
            ]
        )

        paths = []
        for line in sample.splitlines():
            payload = line[3:].strip()
            if " -> " in payload:
                _source, payload = payload.split(" -> ", 1)
            paths.append(ai_guardrail.check_risky_file_registry.normalize_path(payload))

        self.assertEqual(
            paths,
            [
                "src/mediapipeline/tools/dev/refresh_summaries.py",
                "src/mediapipeline/tools/dev/ai_guardrail.py",
                "src/mediapipeline/contracts/lifecycle.py",
            ],
        )


if __name__ == "__main__":
    unittest.main()
