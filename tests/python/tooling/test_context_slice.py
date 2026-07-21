from __future__ import annotations

import json
import unittest

from mediapipeline.tools.dev.context_records import ContextRecord
from mediapipeline.tools.dev.context_slice import (
    build_context_capsule,
    estimate_tokens,
    render_capsule,
)


def _record(path: str, **overrides: object) -> ContextRecord:
    values: dict[str, object] = {
        "path": path,
        "file_type": "Python",
        "purpose": "Own pending publish drain readiness and manifest safety.",
        "owner_domain": "publish",
        "feature_group": "pending-publish",
        "pipeline_stage": "publish",
        "token_priority": "high",
        "source_hash": "b" * 64,
        "evidence_category": "production",
        "layer": "python-domain",
        "authority": "backend-mutation-authority",
        "risk_tier": "high",
        "validation_rung": "targeted publish tests and release gate",
        "relevance_terms": ("pending", "publish", "drain", "readiness", "manifest"),
    }
    values.update(overrides)
    return ContextRecord(**values)


class ContextSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            _record(
                "src/mediapipeline/core/publish/pending_drain.py",
                outbound_dependencies=("src/mediapipeline/core/publish/pending_store.py",),
                associated_tests=("tests/python/desktop/test_pending_publish_drain.py",),
                state_files=("pending_publish_manifest.json",),
            ),
            _record(
                "ops/pipeline/engine/publish/pending_publish.ps1",
                file_type="PowerShell",
                layer="powershell-engine",
                purpose="Park and drain manifest-backed pending outputs.",
            ),
            _record(
                "tests/python/desktop/test_pending_publish_drain.py",
                evidence_category="test",
                layer="tests",
                authority="verification-evidence",
                risk_tier="low",
                token_priority="medium",
            ),
            _record(
                "docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",
                file_type="Markdown",
                evidence_category="documentation",
                layer="boundary-validation-docs",
                authority="canonical-boundary",
                purpose="Defines pending publish and media movement boundaries.",
            ),
            _record(
                "ops/release/changes/unreleased/MP-CHANGE-old.json",
                file_type="JSON",
                evidence_category="change_evidence",
                layer="secondary-evidence",
                authority="historical-evidence",
            ),
        ]

    def test_pending_publish_ranking_returns_vertical_authority_slice(self) -> None:
        capsule = build_context_capsule(
            self.records,
            task="pending publish drain readiness",
            budget=1200,
        )
        paths = {item.record.path for item in capsule.items}

        self.assertEqual(capsule.feature_id, "pending-publish")
        self.assertIn("src/mediapipeline/core/publish/pending_drain.py", paths)
        self.assertIn("ops/pipeline/engine/publish/pending_publish.ps1", paths)
        self.assertIn("tests/python/desktop/test_pending_publish_drain.py", paths)
        self.assertIn("docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md", paths)
        self.assertTrue(capsule.high_risk_relevant)

    def test_default_query_excludes_change_evidence_but_history_flag_includes_it(self) -> None:
        normal = build_context_capsule(self.records, task="pending publish", budget=1200)
        history = build_context_capsule(
            self.records,
            task="pending publish change evidence",
            budget=1200,
            include_history=True,
        )

        self.assertNotIn("change_evidence", {item.record.evidence_category for item in normal.items})
        self.assertIn("change_evidence", {item.record.evidence_category for item in history.items})

    def test_budget_is_enforced_against_final_utf8_bytes(self) -> None:
        records = self.records + [
            _record(
                f"src/mediapipeline/core/publish/secondary_{index}.py",
                purpose="Secondary pending publish implementation evidence " * 4,
                token_priority="low",
            )
            for index in range(30)
        ]
        budget = 500
        capsule = build_context_capsule(records, task="pending publish drain readiness", budget=budget)
        rendered = render_capsule(capsule, output_format="markdown")
        tolerance = max(16, (budget * 2 + 99) // 100)

        self.assertLessEqual(estimate_tokens(rendered), budget + tolerance)
        self.assertGreater(capsule.omitted_count, 0)
        self.assertTrue(capsule.truncation_notes)

    def test_output_is_deterministic_for_input_order_and_json_is_valid(self) -> None:
        first = build_context_capsule(self.records, task="pending publish drain", budget=1000)
        second = build_context_capsule(list(reversed(self.records)), task="pending publish drain", budget=1000)

        first_markdown = render_capsule(first, output_format="markdown")
        second_markdown = render_capsule(second, output_format="markdown")
        self.assertEqual(first_markdown, second_markdown)
        payload = json.loads(render_capsule(first, output_format="json"))
        self.assertEqual(payload["feature_id"], "pending-publish")

    def test_low_confidence_returns_useful_fallback_terms(self) -> None:
        capsule = build_context_capsule(self.records, task="quux frobnicator", budget=500)

        self.assertTrue(capsule.low_confidence)
        self.assertTrue(capsule.suggested_terms)
        self.assertIn("No confident feature match", render_capsule(capsule, output_format="markdown"))

    def test_related_tests_are_selected_even_without_direct_lexical_match(self) -> None:
        capsule = build_context_capsule(self.records, task="manifest drain readiness", budget=1000)
        paths = {item.record.path for item in capsule.items}
        self.assertIn("tests/python/desktop/test_pending_publish_drain.py", paths)


if __name__ == "__main__":
    unittest.main()
