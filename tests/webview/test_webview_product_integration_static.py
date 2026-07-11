from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WEBVIEW = REPO_ROOT / "apps" / "desktop" / "webview" / "static"


class WebViewProductIntegrationStaticTests(unittest.TestCase):
    def test_preset_workflow_uses_all_backend_routes_and_strict_confirmations(self) -> None:
        source = (WEBVIEW / "assets" / "settings" / "presetLibrary.js").read_text(encoding="utf-8")

        for route in (
            "/api/settings/preset-library/validate",
            "/api/settings/preset-library/compare",
            "/api/settings/preset-library/import-preview",
            "/api/settings/preset-library/save",
            "/api/settings/preset-library/export",
            "/api/settings/preset-library/apply-preview",
            "/api/settings/preset-library/apply",
        ):
            self.assertIn(f'"{route}"', source)
        self.assertIn("confirm_save: true", source)
        self.assertIn("confirm_apply: true", source)
        self.assertIn("affects future launches", source.lower())

    def test_recovery_and_support_views_remain_backend_owned(self) -> None:
        source = (WEBVIEW / "assets" / "recoverySupportView.js").read_text(encoding="utf-8")

        self.assertIn('"/api/maintenance/support-export"', source)
        self.assertNotIn("source_path", source)
        self.assertNotIn("destination_path", source)
        self.assertIn("secrets_redacted", source)
        self.assertIn("personal_paths_redacted", source)
        self.assertIn("Startup recovery", source)

    def test_provenance_view_labels_queue_as_non_final_and_completed_as_final_or_legacy(self) -> None:
        source = (WEBVIEW / "assets" / "provenanceView.js").read_text(encoding="utf-8")

        self.assertIn("runtime_effective_settings.v1", source)
        self.assertIn("profile-effective, not final", source)
        self.assertIn("final job-resolved", source)
        self.assertIn("legacy/unavailable", source)


if __name__ == "__main__":
    unittest.main()
