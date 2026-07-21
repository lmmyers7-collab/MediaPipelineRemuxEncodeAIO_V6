from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev.context_extractors import (
    ExtractedSource,
    SUMMARY_GENERATOR_FINGERPRINT,
    SUMMARY_SCHEMA_VERSION,
    extract_source,
)
from mediapipeline.tools.dev.context_records import (
    ContextRecord,
    DEFAULT_EXCLUDED_EVIDENCE,
    REQUIRED_FEATURE_IDS,
    feature_scores,
    records_to_jsonl,
    validate_record_paths,
)


# Independent acceptance fixture: changing production taxonomy cannot silently
# weaken the required feature-card coverage asserted by this test.
EXPECTED_FEATURE_IDS = {
    "tauri-lifecycle",
    "local-api",
    "desktop-application",
    "webview",
    "settings-config",
    "queue-launch",
    "media-processing",
    "subtitles-audio",
    "pending-publish",
    "rename",
    "diagnostics-maintenance",
    "storage-runtime",
    "network-mode",
    "generated-context",
    "release-validation",
}


class ContextExtractorTests(unittest.TestCase):
    def test_python_extracts_fallback_symbols_imports_routes_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pending_publish_service.py"
            path.write_text(
                "import mediapipeline.core.publish.pending_store\n"
                "from .policy import can_drain\n"
                "STATE_FILE = 'pending_publish_manifest.json'\n"
                "@router.post('/api/pending-publish/drain')\n"
                "def drain_pending():\n"
                "    return can_drain()\n",
                encoding="utf-8",
            )

            extracted = extract_source(path, "src/mediapipeline/core/publish/pending_publish_service.py")

            self.assertNotIn("no module docstring", extracted.purpose.lower())
            self.assertIn("drain_pending", extracted.public_symbols)
            self.assertIn("mediapipeline.core.publish.pending_store", extracted.dependencies)
            self.assertTrue(any("pending-publish/drain" in route for route in extracted.api_routes))
            self.assertIn("pending_publish_manifest.json", extracted.state_files)

    def test_javascript_extracts_exports_routes_dom_and_window_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "queueView.js"
            path.write_text(
                "export function renderQueue() {}\n"
                "const refreshQueue = async () => fetch('/api/queue/status');\n"
                "window.MediaPipeline.queue.render = renderQueue;\n"
                "window.MediaPipelineApi.get('/api/queue');\n"
                "document.querySelector('#queue-table');\n",
                encoding="utf-8",
            )

            extracted = extract_source(path, "apps/desktop/webview/static/assets/queueView.js")

            self.assertIn("renderQueue", extracted.public_symbols)
            self.assertIn("refreshQueue", extracted.public_symbols)
            self.assertTrue(any("/api/queue" in route for route in extracted.api_routes))
            self.assertIn("#queue-table", extracted.dom_selectors)
            self.assertIn("window.MediaPipelineApi", extracted.dependencies)
            self.assertNotIn("unparsed", extracted.purpose.lower())

    def test_powershell_extracts_full_dot_source_tools_stages_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "drain_pending.ps1"
            path.write_text(
                ". $PSScriptRoot/../shared/manifest_helpers.ps1\n"
                "$StatePath = 'pending_publish.json'\n"
                "function Invoke-PendingDrain {\n"
                "  Invoke-PipelineStage -Stage Publish\n"
                "  & ffmpeg -version\n"
                "}\n",
                encoding="utf-8",
            )

            extracted = extract_source(path, "ops/pipeline/engine/publish/drain_pending.ps1")

            self.assertIn("Invoke-PendingDrain", extracted.public_symbols)
            self.assertTrue(any("shared/manifest_helpers.ps1" in item for item in extracted.dependencies))
            self.assertIn("Publish", extracted.invoked_stages)
            self.assertIn("ffmpeg", extracted.invoked_tools)
            self.assertIn("pending_publish.json", extracted.state_files)
            self.assertNotIn("synopsis", extracted.purpose.lower())

    def test_rust_has_specific_fallback_and_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "close_readiness.rs"
            path.write_text(
                "#[tauri::command]\npub fn close_ready() -> bool { true }\n",
                encoding="utf-8",
            )

            extracted = extract_source(path, "apps/desktop/tauri/src-tauri/src/close_readiness.rs")

            self.assertIn("close_ready", extracted.public_symbols)
            self.assertIn("Rust", extracted.file_type)
            self.assertNotIn("unparsed", extracted.purpose.lower())

    def test_summary_schema_has_deterministic_parser_fingerprint(self) -> None:
        self.assertGreaterEqual(SUMMARY_SCHEMA_VERSION, 2)
        self.assertRegex(SUMMARY_GENERATOR_FINGERPRINT, r"^[0-9a-f]{64}$")


class ContextRecordTests(unittest.TestCase):
    def _record(self, path: str, **overrides: object) -> ContextRecord:
        values: dict[str, object] = {
            "path": path,
            "file_type": "Python",
            "purpose": "Own pending publish drain readiness.",
            "owner_domain": "publish",
            "feature_group": "pending-publish",
            "pipeline_stage": "publish",
            "token_priority": "high",
            "source_hash": "a" * 64,
            "evidence_category": "production",
            "layer": "python-domain",
            "authority": "backend-mutation-authority",
            "risk_tier": "high",
            "validation_rung": "targeted publish tests and release gate",
        }
        values.update(overrides)
        return ContextRecord(**values)

    def test_jsonl_is_sorted_deterministic_and_compact(self) -> None:
        second = self._record("zeta.py")
        first = self._record("Alpha.py", associated_tests=("tests/test_alpha.py",))

        one = records_to_jsonl([second, first])
        two = records_to_jsonl([first, second])

        self.assertEqual(one, two)
        rows = [json.loads(line) for line in one.splitlines()]
        self.assertEqual([row["path"] for row in rows], ["Alpha.py", "zeta.py"])
        self.assertNotIn("last_modified", rows[0])
        self.assertTrue(one.endswith("\n"))

    def test_record_path_validation_reports_missing_and_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "exists.py").write_text("", encoding="utf-8")
            findings = validate_record_paths(
                [
                    self._record("exists.py"),
                    self._record("missing.py"),
                    self._record(str((root / "absolute.py").resolve())),
                ],
                root,
            )

        self.assertTrue(any("missing.py" in finding for finding in findings))
        self.assertTrue(any("absolute" in finding.lower() for finding in findings))

    def test_default_search_exclusions_are_explicit(self) -> None:
        self.assertEqual(
            DEFAULT_EXCLUDED_EVIDENCE,
            frozenset({"archive", "runtime_artifact", "generated", "change_evidence"}),
        )

    def test_required_feature_taxonomy_cannot_shrink_silently(self) -> None:
        self.assertEqual(set(REQUIRED_FEATURE_IDS), EXPECTED_FEATURE_IDS)

    def test_shared_owner_domain_alone_does_not_pollute_unrelated_features(self) -> None:
        scores = feature_scores(
            "ops/pipeline/engine/process/dynamic_hdr.ps1",
            "process",
            ExtractedSource(file_type="PowerShell", purpose="Detect dynamic HDR metadata."),
        )
        feature_ids = {feature_id for _, feature_id in scores}

        self.assertIn("media-processing", feature_ids)
        self.assertNotIn("tauri-lifecycle", feature_ids)


if __name__ == "__main__":
    unittest.main()
