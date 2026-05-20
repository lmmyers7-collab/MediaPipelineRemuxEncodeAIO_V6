"""
test_tauri_pg1_close_adversarial_scaffold.py

PG-1 adversarial close-readiness scaffold test.

Verifies that the Tauri shell lib.rs contains all required structural patterns for
handling combined active-work + armed-watcher + error close-readiness states. This
is a static scaffold test — it does not run Tauri or require real media.

PG-1 gate criteria (from V5_TAURI_TRANSITION_CURRENT_PLAN.md):
  Adversarial close-readiness: armed watcher + active work + in-flight commands must
  all surface in the Tauri native close-prompt dialog before the operator can dismiss.

This scaffold test proves the lib.rs code satisfies the structural requirements.
Full PG-1 validation requires a live Tauri run with a temporary adversarial backend
(see VALIDATION_LADDER_RUNBOOK.md PG-1 section).

This test does NOT:
  - run Tauri
  - open a window
  - process media
  - post commands
  - mutate any pipeline, settings, queue, rename, or publish state
"""

import unittest
from pathlib import Path

TAURI_SRC_ROOT = Path(__file__).resolve().parents[1] / "tauri_shell" / "src-tauri" / "src"


def _read_tauri_sources() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(TAURI_SRC_ROOT.glob("*.rs")))


class TestTauriPG1CloseAdversarialScaffold(unittest.TestCase):
    """
    PG-1 structural verification for Tauri close-readiness handling.
    """

    def setUp(self):
        self.source = _read_tauri_sources()

    # ------------------------------------------------------------------
    # Struct definitions
    # ------------------------------------------------------------------

    def test_close_readiness_struct_exists(self):
        """CloseReadiness struct must exist with safe_to_close, state, reason, warnings, continuous_watcher."""
        self.assertIn("struct CloseReadiness", self.source)
        self.assertIn("safe_to_close: bool", self.source)
        self.assertIn("continuous_watcher: ContinuousWatcher", self.source)
        self.assertIn("warnings: Vec<String>", self.source)

    def test_continuous_watcher_struct_exists(self):
        """ContinuousWatcher struct must carry all PG-1 relevant fields."""
        self.assertIn("struct ContinuousWatcher", self.source)
        self.assertIn("status: String", self.source)
        self.assertIn("pid: u32", self.source)
        self.assertIn("deadline: String", self.source)
        self.assertIn("stop_requested: bool", self.source)
        self.assertIn("generation: u64", self.source)
        self.assertIn("message: String", self.source)
        self.assertIn("error: String", self.source)

    # ------------------------------------------------------------------
    # Close-readiness detail function
    # ------------------------------------------------------------------

    def test_close_readiness_warning_detail_function_exists(self):
        """close_readiness_warning_detail must exist and handle all PG-1 branches."""
        self.assertIn("fn close_readiness_warning_detail", self.source)

    def test_close_readiness_detail_handles_empty_reason(self):
        """Empty reason must fall back to a generic 'Backend reports active work' message."""
        self.assertIn("Backend reports active work.", self.source)

    def test_close_readiness_detail_includes_warnings_section(self):
        """Warnings section header must appear when warnings are present."""
        self.assertIn('"\\n\\nWarnings:"', self.source)

    def test_close_readiness_detail_includes_watcher_section(self):
        """Watcher section header must appear when watcher status is non-empty."""
        self.assertIn('"\\n\\nContinuous schedule-stop watcher:"', self.source)

    # ------------------------------------------------------------------
    # Watcher-lines function
    # ------------------------------------------------------------------

    def test_close_readiness_watcher_lines_function_exists(self):
        """close_readiness_watcher_lines must exist."""
        self.assertIn("fn close_readiness_watcher_lines", self.source)

    def test_watcher_lines_empty_status_guard(self):
        """Empty watcher status must return no lines."""
        self.assertIn("if status.is_empty()", self.source)
        self.assertIn("return Vec::new()", self.source)

    def test_watcher_lines_pid_guard(self):
        """PID > 0 guard must be present — pid=0 should not produce a pid line."""
        self.assertIn("if watcher.pid > 0", self.source)

    def test_watcher_lines_stop_requested_display(self):
        """stop_requested must be rendered as 'yes'/'no'."""
        self.assertIn('stop requested: {}', self.source)
        self.assertIn('"yes"', self.source)
        self.assertIn('"no"', self.source)

    def test_watcher_lines_generation_display(self):
        """Watcher generation should be rendered when the backend reports one."""
        self.assertIn("watcher.generation > 0", self.source)
        self.assertIn('"generation: {}"', self.source)

    def test_watcher_lines_armed_guard_line(self):
        """Armed watcher must add the in-process guard warning."""
        self.assertIn(
            "closing the backend would remove this in-process stop-at-schedule-boundary guard",
            self.source,
        )
        self.assertIn('status.eq_ignore_ascii_case("armed")', self.source)

    def test_watcher_lines_error_field_shown(self):
        """Watcher error field must be included when non-empty."""
        self.assertIn("watcher.error.trim().is_empty()", self.source)
        # Format string in Rust is "error: {}" — the {} is the placeholder
        self.assertIn('"error: {}"', self.source)

    def test_watcher_lines_message_field_shown(self):
        """Watcher message field must be included when non-empty."""
        self.assertIn("watcher.message.trim().is_empty()", self.source)
        self.assertIn('"message: "', self.source)

    # ------------------------------------------------------------------
    # Schema version validation
    # ------------------------------------------------------------------

    def test_schema_version_validated(self):
        """Schema version must be checked against the known v1 identifier."""
        self.assertIn("desktop_close_readiness.v1", self.source)
        self.assertIn("Unexpected close-readiness schema", self.source)

    # ------------------------------------------------------------------
    # Existing Rust unit tests for PG-1
    # ------------------------------------------------------------------

    def test_rust_unit_test_armed_watcher_detail_exists(self):
        """Rust unit test for armed watcher detail must be present."""
        self.assertIn(
            "fn close_readiness_warning_detail_includes_bounded_watcher_evidence",
            self.source,
        )

    def test_rust_unit_test_structured_watcher_parse_exists(self):
        """Rust unit test for parsing structured watcher evidence must be present."""
        self.assertIn(
            "fn request_close_readiness_parses_structured_watcher_evidence",
            self.source,
        )

    def test_rust_unit_test_combined_active_work_and_armed_watcher_exists(self):
        """PG-1 adversarial: combined active-work reason + armed watcher test must be present."""
        self.assertIn(
            "fn close_readiness_warning_detail_combined_active_work_and_armed_watcher",
            self.source,
        )

    def test_rust_unit_test_stop_requested_shows_yes_exists(self):
        """PG-1 adversarial: stop-requested watcher test must be present."""
        self.assertIn(
            "fn close_readiness_watcher_lines_stop_requested_shows_yes",
            self.source,
        )

    def test_rust_unit_test_error_field_shown_exists(self):
        """PG-1 adversarial: watcher error field test must be present."""
        self.assertIn(
            "fn close_readiness_watcher_lines_error_field_shown",
            self.source,
        )

    def test_rust_unit_test_empty_status_no_lines_exists(self):
        """PG-1 adversarial: empty watcher status returns no lines test must be present."""
        self.assertIn(
            "fn close_readiness_watcher_lines_empty_status_returns_no_lines",
            self.source,
        )

    def test_rust_unit_test_wrong_schema_rejected_exists(self):
        """PG-1 adversarial: wrong schema version rejected test must be present."""
        self.assertIn(
            "fn request_close_readiness_rejects_wrong_schema_version",
            self.source,
        )

    # ------------------------------------------------------------------
    # On-window-event wiring
    # ------------------------------------------------------------------

    def test_on_window_event_close_requested_handler_exists(self):
        """The Tauri on_window_event handler must intercept CloseRequested."""
        self.assertIn("on_window_event", self.source)
        self.assertIn("CloseRequested", self.source)

    def test_safe_to_close_true_allows_close(self):
        """safe_to_close=true must result in the window being allowed to close."""
        self.assertIn("safe_to_close => true", self.source)

    def test_unsafe_close_shows_confirm_dialog(self):
        """safe_to_close=false must present a confirm-close dialog."""
        self.assertIn("confirm_close_dialog", self.source)

    # ------------------------------------------------------------------
    # Mutation guardrail — PG-1 scaffold does NOT test media/pipeline behavior
    # ------------------------------------------------------------------

    def test_close_readiness_calls_correct_route(self):
        """request_close_readiness must call the close-readiness route, not a pipeline route."""
        # The close-readiness request must call /api/backend/close-readiness
        self.assertIn("/api/backend/close-readiness", self.source)
        # The close_readiness_warning_detail function must not reference pipeline start
        detail_fn_start = self.source.find("fn close_readiness_warning_detail")
        detail_fn_end = self.source.find("\nfn ", detail_fn_start + 1)
        detail_fn_body = self.source[detail_fn_start:detail_fn_end]
        self.assertNotIn("/api/pipeline/start", detail_fn_body)


if __name__ == "__main__":
    unittest.main()
