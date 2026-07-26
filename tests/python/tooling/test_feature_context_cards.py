from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev.context_records import ContextRecord
from mediapipeline.tools.dev.context_slice import estimate_tokens
from mediapipeline.tools.dev.generate_feature_file_map import (
    feature_card_path,
    render_feature_cards,
    write_or_check_cards,
)


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


def _record(feature_id: str, layer: str, path: str, category: str = "production") -> ContextRecord:
    return ContextRecord(
        path=path,
        file_type="Python",
        purpose=f"Authority surface for {feature_id}.",
        owner_domain=feature_id,
        feature_group=feature_id,
        pipeline_stage="n/a",
        token_priority="high" if category == "production" else "medium",
        source_hash="c" * 64,
        evidence_category=category,
        layer=layer,
        authority="backend-authority" if category == "production" else "verification-evidence",
        risk_tier="low",
        validation_rung="targeted unit tests",
        relevance_terms=tuple(feature_id.split("-")),
    )


class FeatureContextCardTests(unittest.TestCase):
    def test_every_required_feature_has_compact_vertical_card(self) -> None:
        records: list[ContextRecord] = []
        for feature_id in sorted(EXPECTED_FEATURE_IDS):
            records.extend(
                [
                    _record(feature_id, "webview-tauri", f"apps/{feature_id}.js"),
                    _record(feature_id, "local-api", f"src/api/{feature_id}.py"),
                    _record(feature_id, "python-domain", f"src/core/{feature_id}.py"),
                    _record(feature_id, "powershell-engine", f"ops/{feature_id}.ps1"),
                    _record(feature_id, "tests", f"tests/test_{feature_id}.py", "test"),
                ]
            )

        cards = render_feature_cards(records)

        self.assertEqual(set(cards), EXPECTED_FEATURE_IDS)
        for feature_id, text in cards.items():
            with self.subTest(feature=feature_id):
                self.assertIn("Vertical slice", text)
                self.assertIn("Why these files", text)
                self.assertIn("Tests and validation", text)
                self.assertLessEqual(estimate_tokens(text), 1200)

    def test_cards_are_deterministic_checkable_and_remove_unexpected_files(self) -> None:
        records = [
            _record(feature_id, "python-domain", f"src/core/{feature_id}.py")
            for feature_id in sorted(EXPECTED_FEATURE_IDS)
        ]
        cards = render_feature_cards(records)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertTrue(write_or_check_cards(cards, root, check=False))
            self.assertTrue(write_or_check_cards(cards, root, check=True))
            stale = feature_card_path(root, "pending-publish")
            stale.write_text("stale", encoding="utf-8")
            self.assertFalse(write_or_check_cards(cards, root, check=True))
            stale.write_text(cards["pending-publish"], encoding="utf-8", newline="\n")
            (root / "unexpected.md").write_text("unexpected", encoding="utf-8")
            self.assertFalse(write_or_check_cards(cards, root, check=True))


if __name__ == "__main__":
    unittest.main()
