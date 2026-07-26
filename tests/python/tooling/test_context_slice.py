from __future__ import annotations

import json
import unittest

from mediapipeline.tools.dev.context_records import ContextRecord, load_records
from mediapipeline.tools.dev.context_slice import (
    DEFAULT_INDEX_PATH,
    build_context_capsule,
    estimate_tokens,
    rank_records,
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

    def test_generic_ai_token_cleanup_prefers_generated_context_tooling(self) -> None:
        records = [
            _record(
                "src/mediapipeline/tools/dev/context_slice.py",
                purpose="Return a deterministic token-bounded repository context capsule.",
                owner_domain="scripts",
                feature_group="generated-context",
                risk_tier="low",
            ),
            _record(
                "src/mediapipeline/tools/dev/context_records.py",
                purpose="Build the typed catalog for generated AI navigation.",
                owner_domain="scripts",
                feature_group="generated-context",
                risk_tier="low",
            ),
            _record(
                "src/mediapipeline/tools/dev/context_extractors.py",
                purpose="Extract deterministic repository metadata.",
                owner_domain="scripts",
                feature_group="generated-context",
                risk_tier="low",
            ),
            _record(
                "apps/desktop/webview/static/assets/settings/cleanup.js",
                file_type="JavaScript",
                purpose="Cleanup sources in the settings view.",
                layer="webview-tauri",
                owner_domain="webview",
                feature_group="webview",
                public_symbols=("cleanup",),
                risk_tier="low",
            ),
            _record(
                "src/mediapipeline/desktop/api/source_cleanup.py",
                purpose="Expose API cleanup sources.",
                layer="local-api",
                owner_domain="api",
                feature_group="local-api",
                risk_tier="low",
            ),
            _record(
                "ops/pipeline/engine/failures/cleanup.ps1",
                file_type="PowerShell",
                purpose="Cleanup failed source artifacts.",
                layer="powershell-engine",
                owner_domain="process",
                feature_group="media-processing",
            ),
        ]
        task = "Identify codebase-specific sources of excessive AI token usage and cleanup opportunities."
        capsule = build_context_capsule(records, task=task, budget=1000)
        paths = [item.record.path for item in capsule.items]

        self.assertEqual(paths[:3], [
            "src/mediapipeline/tools/dev/context_slice.py",
            "src/mediapipeline/tools/dev/context_records.py",
            "src/mediapipeline/tools/dev/context_extractors.py",
        ])
        self.assertFalse(any("webview" in path or "/api/" in path or path.endswith("cleanup.ps1") for path in paths))
        self.assertTrue(capsule.omission_reasons)

    def test_precise_symbol_match_outranks_generic_feature_membership(self) -> None:
        direct = _record(
            "src/mediapipeline/tools/dev/context_slice.py",
            purpose="Build task capsules.",
            owner_domain="scripts",
            feature_group="generated-context",
            public_symbols=("build_context_capsule",),
            risk_tier="low",
        )
        generic = _record(
            "src/mediapipeline/tools/dev/other_tool.py",
            purpose="Generated context helper.",
            owner_domain="scripts",
            feature_group="generated-context",
            public_symbols=("build_capsule_report",),
            risk_tier="low",
        )

        _, _, ranked = rank_records([generic, direct], task="Change build_context_capsule deterministically")

        self.assertEqual(ranked[0].record.path, direct.path)
        self.assertTrue(any(reason.startswith("exact public symbol:") for reason in ranked[0].reasons))
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_media_policy_intent_prefers_engine_and_sets_high_risk(self) -> None:
        engine = _record(
            "ops/pipeline/engine/process/ffmpeg_stream_map.ps1",
            file_type="PowerShell",
            purpose="Own FFmpeg stream mapping and media policy.",
            layer="powershell-engine",
            owner_domain="process",
            feature_group="media-processing",
            relevance_terms=("ffmpeg", "stream", "mapping", "media", "policy"),
        )
        ui = _record(
            "apps/desktop/webview/static/assets/media/policy.js",
            file_type="JavaScript",
            purpose="Display FFmpeg stream mapping policy status.",
            layer="webview-tauri",
            owner_domain="webview",
            feature_group="webview",
            authority="frontend-display-and-intent",
            risk_tier="low",
            relevance_terms=("ffmpeg", "stream", "mapping", "media", "policy"),
        )
        capsule = build_context_capsule(
            [ui, engine],
            task="Fix high-risk FFmpeg stream mapping media policy",
            budget=800,
        )

        self.assertEqual(capsule.items[0].record.path, engine.path)
        self.assertTrue(capsule.high_risk_relevant)
        self.assertGreater(capsule.items[0].score, next(item.score for item in rank_records([ui, engine], task="Fix high-risk FFmpeg stream mapping media policy")[2] if item.record.path == ui.path))

    def test_documentation_only_request_excludes_implementation_and_tests(self) -> None:
        docs = _record(
            "docs/architecture/GENERATED_CONTEXT.md",
            file_type="Markdown",
            purpose="Document generated context navigation.",
            evidence_category="documentation",
            layer="boundary-validation-docs",
            authority="canonical-boundary",
            feature_group="generated-context",
            risk_tier="low",
        )
        production = _record(
            "src/mediapipeline/tools/dev/context_slice.py",
            purpose="Implement generated context navigation.",
            owner_domain="scripts",
            feature_group="generated-context",
            risk_tier="low",
        )
        test = _record(
            "tests/python/tooling/test_context_slice.py",
            purpose="Test generated context navigation.",
            evidence_category="test",
            layer="tests",
            authority="verification-evidence",
            owner_domain="tests",
            feature_group="generated-context",
            risk_tier="low",
        )

        capsule = build_context_capsule(
            [production, test, docs],
            task="Documentation only: update the generated context guide",
            budget=700,
        )

        self.assertEqual([item.record.path for item in capsule.items], [docs.path])

    def test_intent_classifier_routes_docs_tooling_ui_api_tests_and_engine(self) -> None:
        records = [
            _record(
                "docs/operator/status.md",
                file_type="Markdown",
                purpose="Describe shared status behavior.",
                evidence_category="documentation",
                layer="boundary-validation-docs",
                authority="canonical-boundary",
                feature_group="diagnostics-maintenance",
                risk_tier="low",
            ),
            _record(
                "src/mediapipeline/tools/dev/status_report.py",
                purpose="Generate shared status behavior reports.",
                owner_domain="scripts",
                feature_group="generated-context",
                risk_tier="low",
            ),
            _record(
                "apps/desktop/webview/static/assets/status/view.js",
                file_type="JavaScript",
                purpose="Display shared status behavior.",
                layer="webview-tauri",
                owner_domain="webview",
                feature_group="webview",
                authority="frontend-display-and-intent",
                risk_tier="low",
            ),
            _record(
                "src/mediapipeline/desktop/api/status_route.py",
                purpose="Expose shared status behavior through an endpoint.",
                layer="local-api",
                owner_domain="api",
                feature_group="local-api",
                risk_tier="low",
            ),
            _record(
                "tests/python/desktop/test_status_behavior.py",
                purpose="Verify shared status behavior.",
                evidence_category="test",
                layer="tests",
                authority="verification-evidence",
                owner_domain="tests",
                feature_group="diagnostics-maintenance",
                risk_tier="low",
            ),
            _record(
                "ops/pipeline/engine/status/media_status.ps1",
                file_type="PowerShell",
                purpose="Compute shared media status behavior.",
                layer="powershell-engine",
                owner_domain="process",
                feature_group="media-processing",
            ),
        ]
        cases = {
            "Update docs for shared status behavior": "docs/operator/status.md",
            "Update tooling for shared status behavior": "src/mediapipeline/tools/dev/status_report.py",
            "Update UI for shared status behavior": "apps/desktop/webview/static/assets/status/view.js",
            "Update API for shared status behavior": "src/mediapipeline/desktop/api/status_route.py",
            "Add tests for shared status behavior": "tests/python/desktop/test_status_behavior.py",
            "Update media engine for shared status behavior": "ops/pipeline/engine/status/media_status.ps1",
        }

        for task, expected_path in cases.items():
            with self.subTest(task=task):
                _, _, ranked = rank_records(records, task=task)
                self.assertEqual(ranked[0].record.path, expected_path)

    def test_budget_smaller_than_one_normal_record_returns_compact_capsule(self) -> None:
        record = _record(
            "src/mediapipeline/tools/dev/context_slice.py",
            purpose="Very detailed generated context purpose. " * 40,
            owner_domain="scripts",
            feature_group="generated-context",
            risk_tier="low",
        )
        capsule = build_context_capsule([record], task="context slice token budget", budget=200)
        rendered = render_capsule(capsule)

        self.assertLessEqual(estimate_tokens(rendered), 200)
        self.assertEqual(capsule.estimated_tokens, estimate_tokens(rendered))
        self.assertTrue(capsule.omission_reasons or capsule.items)

    def test_strict_limits_hold_for_repeated_markdown_and_json_execution(self) -> None:
        records = self.records * 8
        for output_format in ("markdown", "json"):
            for budget in (200, 350, 500, 1000):
                rendered_outputs = []
                for _ in range(3):
                    capsule = build_context_capsule(
                        records,
                        task="pending publish drain media policy",
                        budget=budget,
                        output_format=output_format,
                    )
                    rendered = render_capsule(capsule, output_format=output_format)
                    self.assertLessEqual(estimate_tokens(rendered), budget)
                    self.assertEqual(capsule.estimated_tokens, estimate_tokens(rendered))
                    rendered_outputs.append(rendered)
                self.assertEqual(len(set(rendered_outputs)), 1)

    def test_repository_baseline_stays_strict_and_excludes_unrelated_domains(self) -> None:
        task = "Identify codebase-specific sources of excessive AI token usage and cleanup opportunities."
        capsule = build_context_capsule(load_records(DEFAULT_INDEX_PATH), task=task, budget=2000)
        rendered = render_capsule(capsule)
        paths = [item.record.path for item in capsule.items]

        self.assertLessEqual(estimate_tokens(rendered), 2000)
        self.assertEqual(paths[:3], [
            "src/mediapipeline/tools/dev/context_slice.py",
            "src/mediapipeline/tools/dev/context_records.py",
            "src/mediapipeline/tools/dev/context_extractors.py",
        ])
        self.assertFalse(any(path.startswith("apps/desktop/webview/") for path in paths))
        self.assertFalse(any(path.startswith("src/mediapipeline/desktop/api/") for path in paths))
        self.assertFalse(any(path.startswith("ops/pipeline/engine/") for path in paths))

    def test_active_tier_prefilters_unrelated_records_and_all_is_explicit(self) -> None:
        unrelated = [
            _record(
                f"src/mediapipeline/core/queue/unrelated_{index}.py",
                purpose="Render unrelated queue inventory rows.",
                owner_domain="queue",
                feature_group="queue-launch",
                feature_groups=("queue-launch",),
                relevance_terms=("queue", "inventory", "rows"),
                risk_tier="low",
            )
            for index in range(12)
        ]
        generated = _record(
            "docs/generated/WEBVIEW_TOUCHPOINT_LEDGER.json",
            file_type="JSON",
            evidence_category="generated",
            layer="secondary-evidence",
            authority="secondary-evidence",
            risk_tier="low",
        )
        fixture = _record(
            "tests/fixtures/pending_publish_snapshot.json",
            file_type="JSON",
            evidence_category="test",
            layer="tests",
            authority="verification-evidence",
            risk_tier="low",
        )
        records = self.records + unrelated + [generated, fixture]

        active = build_context_capsule(records, task="pending publish drain readiness", budget=1200)
        all_evidence = build_context_capsule(
            records,
            task="pending publish drain readiness",
            budget=1200,
            retrieval_tier="all",
        )

        self.assertEqual(active.retrieval_stats.tier, "active")
        self.assertLess(active.retrieval_stats.candidate_count, active.retrieval_stats.eligible_count)
        self.assertNotIn(generated.path, {item.record.path for item in active.items})
        self.assertNotIn(fixture.path, {item.record.path for item in active.items})
        self.assertEqual(all_evidence.retrieval_stats.eligible_count, len(records))
        self.assertGreater(all_evidence.retrieval_stats.candidate_count, active.retrieval_stats.candidate_count)

    def test_exact_symbol_bypasses_active_history_exclusion(self) -> None:
        historical = _record(
            "ops/release/changes/unreleased/MP-CHANGE-historical.json",
            file_type="JSON",
            evidence_category="change_evidence",
            layer="secondary-evidence",
            authority="secondary-evidence",
            risk_tier="low",
            public_symbols=("historical_policy_symbol",),
            relevance_terms=("historical", "policy", "symbol"),
        )

        capsule = build_context_capsule(
            self.records + [historical],
            task="historical_policy_symbol",
            budget=700,
        )

        self.assertIn(historical.path, {item.record.path for item in capsule.items})
        self.assertEqual(capsule.retrieval_stats.tier, "active")


if __name__ == "__main__":
    unittest.main()
