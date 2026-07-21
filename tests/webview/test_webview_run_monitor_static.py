from __future__ import annotations

import re
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
STATIC_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"


class WebViewRunMonitorStaticTests(unittest.TestCase):
    def test_home_exposes_one_primary_file_centric_current_work_surface(self) -> None:
        markup = (STATIC_ROOT / "partials" / "page-home.html").read_text(encoding="utf-8")
        app_shell = (STATIC_ROOT / "partials" / "app-shell-start.html").read_text(encoding="utf-8")
        match = re.search(
            r'<section[^>]+data-primary-current-work[^>]*>(.*?)</section>\s*<!--\s*end primary current work\s*-->',
            markup,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "Home must expose a bounded primary Current Work section.")
        current_work = match.group(1)
        for required in (
            'id="current-work-heading"',
            ">Current Work<",
            'id="run-monitor-summary"',
            'id="run-monitor-outcome"',
            'id="run-monitor-workers"',
            'id="run-monitor-items"',
            'id="run-monitor-detail"',
            'id="run-monitor-stage-list"',
            'id="run-monitor-audio-body"',
            'id="run-monitor-subtitle-body"',
            'id="run-monitor-terminal-links"',
            'id="run-monitor-last-known"',
            'data-control-action="stop"',
            ">Stop After Current<",
        ):
            self.assertIn(required, current_work)
        self.assertEqual(current_work.count('aria-live="polite"'), 1)
        self.assertIn('id="run-monitor-announcer"', current_work)
        self.assertNotIn('role="listbox"', current_work)
        self.assertNotRegex(app_shell, r'id="(?:topbar-event-ticker|floating-pipeline-log-text)"[^>]+aria-live')

        for retired in (
            "legacy-status-metrics",
            "legacy-quick-controls",
            "legacy-live-run",
            "legacy-next-five",
            "legacy-run-progress",
            "legacy-recent-completed",
        ):
            self.assertRegex(markup, rf'hidden[^>]+data-run-monitor-retired="{retired}"')

    def test_run_monitor_module_uses_only_backend_projection_for_current_claims(self) -> None:
        script = (STATIC_ROOT / "assets" / "runMonitorView.js").read_text(encoding="utf-8")
        for required in (
            'desktop_run_monitor.v1',
            '"/api/run-monitor"',
            'desktop_run_monitor_launch.v1',
            'backend_accepted',
            'awaiting_engine_confirmation',
            'Last known — not current',
            'Planned route',
            'Planned reason',
            'Executed route',
            'Executed reason',
            'Final route',
            'Final reason',
            'current_workers',
            'ArrowDown',
            'ArrowUp',
            'Home',
            'End',
            'aria-current',
            'data-run-monitor-job-id',
            "trackTimingLabel",
            "run-monitor-outcome",
        ):
            self.assertIn(required, script)
        for forbidden in (
            "CurrentRoute",
            "CurrentFile",
            "CurrentStage",
            "recent_events",
            "stdout_tail",
            "filename similarity",
            "includes(\"encode\")",
            "includes(\"remux\")",
        ):
            self.assertNotIn(forbidden, script)

    def test_retired_home_next_five_has_no_current_work_projection(self) -> None:
        home = (STATIC_ROOT / "assets" / "app" / "home.js").read_text(encoding="utf-8")
        projection = (STATIC_ROOT / "assets" / "app" / "home" / "queueProjection.js").read_text(encoding="utf-8")
        refresh = (STATIC_ROOT / "assets" / "app" / "refreshCoordinator.js").read_text(encoding="utf-8")

        for forbidden in (
            "homeQueueItemMatchesActiveWork",
            "homeCurrentQueueRow",
            "homeCurrentQueueOrder",
            "homeProgressCurrentSourceKey",
            "homeTextMatchKey",
            "counts.processed",
        ):
            self.assertNotIn(forbidden, projection)
            self.assertNotIn(forbidden, home)
        self.assertNotIn("renderHomeNextQueue(dashboardContext)", refresh)
        self.assertNotIn("renderHomeNextQueue({ ...liveRunContext, queue: lastQueue || {} })", refresh)

    def test_accepted_workload_defaults_to_twenty_name_preview_rows_before_selection_expands(self) -> None:
        markup = (STATIC_ROOT / "partials" / "page-home.html").read_text(encoding="utf-8")
        script = (STATIC_ROOT / "assets" / "runMonitorView.js").read_text(encoding="utf-8")
        styles = (STATIC_ROOT / "assets" / "styles" / "pages" / "home.css").read_text(encoding="utf-8")

        self.assertIn('id="run-monitor-items-toggle"', markup)
        self.assertIn('aria-controls="run-monitor-items"', markup)
        self.assertIn('aria-expanded="false"', markup)
        self.assertIn('role="region"', markup)
        self.assertIn("verified backend production naming plan", markup)
        self.assertIn('const VERIFIED_DISPLAY_NAME_SOURCE = "plex_destination_plan.v1"', script)
        self.assertIn('"terminal_output"', script)
        self.assertIn("correlated terminal output evidence", script)
        self.assertIn("File name authority:", script)
        self.assertIn("File name evidence:", script)
        self.assertIn("saved run predates verified cleaned-name evidence", script)
        self.assertIn("refresh Queue and launch a new Backend Queue Run Once", script)
        self.assertNotIn("backend preserves the source filename", markup)
        self.assertIn("const COMPACT_ITEM_LIMIT = 20", script)
        self.assertIn("workloadExpanded", script)
        self.assertIn("run-monitor-item-preview", script)
        self.assertIn(".run-monitor-item-preview", styles)
        self.assertNotIn("split(\".\")", script)

    def test_run_monitor_script_and_focus_navigation_contract_are_wired(self) -> None:
        index = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        navigation = (STATIC_ROOT / "assets" / "app" / "lifecycle" / "navigation.js").read_text(encoding="utf-8")
        lifecycle = (STATIC_ROOT / "assets" / "app" / "lifecycle.js").read_text(encoding="utf-8")
        launch = (STATIC_ROOT / "assets" / "launch" / "commandOrchestration.js").read_text(encoding="utf-8")
        self.assertIn('<script defer src="/assets/runMonitorView.js"></script>', index)
        self.assertIn("focusPageDestination", navigation)
        self.assertIn("navigateToPage", navigation)
        self.assertIn("focusPageDestination", lifecycle)
        self.assertIn("navigateToPage", lifecycle)
        self.assertIn("acceptLaunchResult", launch)

    def test_legacy_progress_cannot_compete_with_current_work_authority(self) -> None:
        timeline = (STATIC_ROOT / "assets" / "progress" / "timelineView.js").read_text(encoding="utf-8")
        core = (STATIC_ROOT / "assets" / "progress" / "timelineCore.js").read_text(encoding="utf-8")
        live_run = (STATIC_ROOT / "assets" / "progress" / "liveRun.js").read_text(encoding="utf-8")
        home = (STATIC_ROOT / "partials" / "page-home.html").read_text(encoding="utf-8")
        self.assertNotIn('stageMentions(routeLower, "encode"', timeline)
        self.assertIn("Audio evidence unknown; no pending state is inferred.", timeline)
        self.assertIn("Subtitle evidence unknown; no pending state is inferred.", timeline)
        self.assertIn("route text is not stage authority", timeline)
        self.assertNotIn("completedEvent", core)
        self.assertNotIn('"encode_verify", "remux_av", "remux_verify"', live_run)
        self.assertIn('["encode_verify", "remux_verify"].includes(normalizedStage) ? "Verification"', live_run)
        self.assertNotIn('data-quick-link-page="live"', home)

    def test_current_work_styles_cover_focus_reflow_and_reduced_motion(self) -> None:
        styles = (STATIC_ROOT / "assets" / "styles" / "pages" / "home.css").read_text(encoding="utf-8")
        monitor_styles = styles[styles.index("/* Backend-owned Run Once monitor.") :]
        for required in (
            ".run-monitor-item-button:focus-visible",
            "outline: 3px solid",
            "@media (max-width: 900px)",
            "@media (max-width: 390px)",
            "overflow-wrap: anywhere",
            ".run-monitor-track-table td::before",
            "content: attr(data-label)",
            "prefers-reduced-motion: reduce",
        ):
            self.assertIn(required, styles)
        self.assertNotRegex(monitor_styles, r"(?m)^\s+color: var\(--grey-500\)")

    def test_manual_accessibility_script_covers_folded_clean_name_workflow(self) -> None:
        script = (REPO_ROOT / "docs" / "operator" / "WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md").read_text(
            encoding="utf-8"
        )
        normalized_script = " ".join(script.split())
        for required in (
            "first 20 verified cleaned filenames",
            "noninteractive preview rows",
            "Open file selection",
            "every accepted file exactly once",
            "raw source path as secondary accessible identity evidence",
            "collapse focus returns to the disclosure button",
            "must not trigger a new focus event",
            "active → quiet → the same file active again",
        ):
            self.assertIn(required, normalized_script)

    def test_monitor_preserves_dynamic_focus_and_uses_plural_active_file_semantics(self) -> None:
        monitor = (STATIC_ROOT / "assets" / "runMonitorView.js").read_text(encoding="utf-8")
        for required in (
            "captureDynamicMonitorFocus",
            "restoreDynamicMonitorFocus",
            "data-run-monitor-worker-id",
            "data-run-monitor-terminal-key",
            'identity.dataset.label = "Track"',
            'source.dataset.label = "Source"',
            'planned.dataset.label = "Planned action"',
            'current.dataset.label = "Current / final evidence"',
        ):
            self.assertIn(required, monitor)
        self.assertNotIn('if (current) button.setAttribute("aria-current", "true")', monitor)

    def test_topbar_defers_backend_queue_current_claims_to_run_monitor(self) -> None:
        topbar = (STATIC_ROOT / "assets" / "app" / "lifecycle" / "topbar.js").read_text(encoding="utf-8")
        lifecycle = (STATIC_ROOT / "assets" / "app" / "lifecycle.js").read_text(encoding="utf-8")
        monitor = (STATIC_ROOT / "assets" / "runMonitorView.js").read_text(encoding="utf-8")
        launch = (STATIC_ROOT / "assets" / "launch" / "commandOrchestration.js").read_text(encoding="utf-8")
        self.assertIn("topbarBackendQueueMonitorContext", topbar)
        self.assertIn("topbarSnapshotProvesDifferentWorkflow", topbar)
        self.assertIn("topbarSnapshotIsFreshlyActive", topbar)
        self.assertIn("topbarSnapshotProvesSameBackendQueueRun", topbar)
        self.assertIn("Correlated Monitor Unavailable", topbar)
        self.assertIn('node.dataset.authority = "run_monitor"', topbar)
        self.assertIn("No file, stage, route, or percent claim", topbar)
        self.assertIn("Supporting telemetry — latest backend event", topbar)
        self.assertIn("Not current-work authority", topbar)
        self.assertIn('"mediapipeline:run-monitor-rendered"', lifecycle)
        self.assertIn("backendQueueCorrelationContext", monitor)
        self.assertIn("clearBackendQueueContext", monitor)
        self.assertIn("standardBackendQueueRun", launch)
        self.assertIn("clearBackendQueueContext", launch)

    def test_terminal_proof_handoff_waits_for_correlated_async_rows(self) -> None:
        monitor = (STATIC_ROOT / "assets" / "runMonitorView.js").read_text(encoding="utf-8")
        self.assertIn("beginTerminalHandoff", monitor)
        self.assertIn("MutationObserver", monitor)
        self.assertIn("terminalHandoffTarget?.isConnected", monitor)
        self.assertIn("terminalReferenceMatch", monitor)
        self.assertNotIn("filename", monitor[monitor.index("function terminalReferenceMatch"):monitor.index("function focusTerminalHeading")].lower())

    def test_large_queue_uses_one_roving_row_tab_stop_and_full_identity_label(self) -> None:
        table = (STATIC_ROOT / "assets" / "queue" / "table.js").read_text(encoding="utf-8")
        table_view = (STATIC_ROOT / "assets" / "queue" / "tableView.js").read_text(encoding="utf-8")
        shared = (STATIC_ROOT / "assets" / "dom" / "table.js").read_text(encoding="utf-8")
        self.assertIn("roving: true", table)
        self.assertIn("rovingTabStop", table)
        self.assertIn("item.source_path", table)
        self.assertIn('button.dataset.queueRowAction = "file-overrides"', table)
        self.assertIn("button.tabIndex = rovingTabStop ? 0 : -1", table)
        self.assertIn("row.tabIndex = options.rovingTabStop ? 0 : -1", shared)
        self.assertIn("row.tabIndex = key === selectedRowKey ? 0 : -1", table_view)
        self.assertIn("rowAction.tabIndex = key === selectedRowKey ? 0 : -1", table_view)

    def test_queue_labels_predictive_evidence_as_planned(self) -> None:
        markup = (STATIC_ROOT / "partials" / "page-queue.html").read_text(encoding="utf-8")
        table = (STATIC_ROOT / "assets" / "queue" / "table.js").read_text(encoding="utf-8")
        detail = (STATIC_ROOT / "assets" / "queueView.detail.js").read_text(encoding="utf-8")
        self.assertIn('<th scope="col">Planned route</th>', markup)
        self.assertIn('<th scope="col">Planned reason</th>', markup)
        self.assertIn('"Planned route"', table)
        self.assertIn("Planned route:", detail)
        self.assertIn("Planned reason:", detail)


if __name__ == "__main__":
    unittest.main()
