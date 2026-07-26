from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "assets"


def _read_asset(relative_path: str) -> str:
    return (ASSETS_ROOT / relative_path).read_text(encoding="utf-8")


def _listener_pattern(control_id: str, event_name: str) -> re.Pattern[str]:
    return re.compile(
        rf'const\s+(?P<variable>[A-Za-z_$][\w$]*)\s*=\s*byId\("{re.escape(control_id)}"\);\s*'
        rf'if\s*\(\s*(?P=variable)\s*\)\s*(?P=variable)\.addEventListener\("{event_name}"',
        re.MULTILINE,
    )


class WebViewEventListenerOwnershipTests(unittest.TestCase):
    def test_pending_filter_listeners_are_owned_only_by_pending_action_center(self) -> None:
        orchestration = _read_asset("app/lifecycleOrchestration.js")
        pending_action_center = _read_asset("pendingPublish/actionCenter.js")

        for control_id, event_name in (
            ("pending-filter", "input"),
            ("pending-status-filter", "change"),
            ("pending-investigation-filter", "change"),
            ("pending-clear-filters-button", "click"),
        ):
            with self.subTest(control_id=control_id):
                pattern = _listener_pattern(control_id, event_name)
                self.assertRegex(pending_action_center, pattern)
                self.assertNotRegex(orchestration, pattern)

    def test_failure_filter_listener_is_owned_only_by_reports(self) -> None:
        orchestration = _read_asset("app/lifecycleOrchestration.js")
        reports_view = _read_asset("reportsView.js")
        pattern = _listener_pattern("failure-filter", "input")

        self.assertRegex(reports_view, pattern)
        self.assertNotRegex(orchestration, pattern)

    def test_generated_row_open_actions_have_one_delegated_owner_and_backend_availability_state(self) -> None:
        row_actions = _read_asset("app/rowOpenActions.js")
        completed_selection = _read_asset("completed/selection.js")
        pending_details = _read_asset("pendingPublish/details.js")
        queue_details = _read_asset("queueView.detail.js")

        self.assertEqual(row_actions.count('document.addEventListener("click", handleBackendRowOpenAction'), 1)
        self.assertIn("if (!button || !container || button.disabled) return;", row_actions)
        self.assertIn("setBackendRowOpenActionAvailability", row_actions)
        self.assertIn("setBackendRowOpenActionBusy", row_actions)
        self.assertIn('setBackendRowOpenActionAvailability(container.dataset.openTargetRowActions || "", []);', row_actions)
        self.assertIn('"completed",\n        item?.available_open_targets', completed_selection)
        self.assertIn('"pending",\n      item?.available_open_targets', pending_details)
        self.assertIn('"queue",\n        item?.available_open_targets', queue_details)
        self.assertIn('"queue-excluded",\n        item?.available_open_targets', queue_details)


if __name__ == "__main__":
    unittest.main()
