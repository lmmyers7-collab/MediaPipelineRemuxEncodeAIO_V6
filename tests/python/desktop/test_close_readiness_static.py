from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))


class CloseReadinessStaticTests(unittest.TestCase):
    def test_frontend_treats_stale_state_as_non_blocking(self) -> None:
        static_root = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static"
        close_readiness_js = (static_root / "assets" / "app" / "closeReadiness.js").read_text(encoding="utf-8")

        self.assertIn('["idle", "completed", "failed", "stale"]', close_readiness_js)

    def test_frontend_normalizes_invalid_close_readiness_fail_closed(self) -> None:
        static_root = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static"
        close_readiness_js = (static_root / "assets" / "app" / "closeReadiness.js").read_text(encoding="utf-8")
        app_js = (static_root / "assets" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function normalizeCloseReadiness", close_readiness_js)
        self.assertIn("typeof payload.safe_to_close !== \"boolean\"", close_readiness_js)
        self.assertIn("safe_to_close: false", close_readiness_js)
        self.assertIn("operator_status: \"unavailable\"", close_readiness_js)
        self.assertIn("normalizeCloseReadiness", app_js)
        self.assertIn("renderCloseReadinessUnavailable", app_js)


if __name__ == "__main__":
    unittest.main()
