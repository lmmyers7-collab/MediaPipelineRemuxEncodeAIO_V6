from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from html.parser import HTMLParser
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_browser_queue_file_overrides_smoke import (
        _run_browser_queue_file_overrides_smoke,
    )
    from .test_webview_browser_rename_smoke import _run_browser_rename_smoke
    from .test_webview_real_media_smoke import _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_browser_queue_file_overrides_smoke import (
        _run_browser_queue_file_overrides_smoke,
    )
    from test_webview_browser_rename_smoke import _run_browser_rename_smoke
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )


EXPECTED_STATIC_COUNTS = {
    "shell": 32,
    "launch": 38,
    "queue": 99,
    "rename": 39,
}
EXPECTED_CLASSIFICATION_TOTALS = {
    "discovered": 208,
    "skipped": 18,
    "failed": 0,
    "unclassified": 0,
}
EXPECTED_CLASSIFICATION_SPLITS = {(159, 31), (160, 30)}
EXPECTED_GENERATED_TOTALS = {
    "discovered": 169,
    "activated": 169,
    "blocked": 0,
}


_INTERACTIVE_TAGS = {"button", "input", "select", "textarea", "summary"}
_INTERACTIVE_ROLES = {
    "button",
    "link",
    "checkbox",
    "radio",
    "switch",
    "tab",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "option",
    "treeitem",
    "gridcell",
    "row",
}
_STABLE_DATA_ATTRIBUTES = (
    "data-page",
    "data-pipeline-mode-preset",
    "data-cross-page-target",
    "data-pipeline-scope-preset",
    "data-control-action",
    "data-fo-use-inherited",
    "data-fo-series-filter",
)


class _SourceControlParser(HTMLParser):
    def __init__(self, surface: str) -> None:
        super().__init__(convert_charrefs=True)
        self.surface = surface
        self.controls: list[dict[str, object]] = []
        self._active: list[dict[str, object]] = []

    @staticmethod
    def _is_interactive(tag: str, attrs: dict[str, str]) -> bool:
        if tag in _INTERACTIVE_TAGS:
            return True
        if tag == "a" and "href" in attrs:
            return True
        if attrs.get("role", "").strip().lower() in _INTERACTIVE_ROLES:
            return True
        if "tabindex" in attrs:
            try:
                return int(attrs["tabindex"]) >= 0
            except ValueError:
                return False
        return False

    def handle_starttag(self, tag: str, raw_attrs: list[tuple[str, str | None]]) -> None:
        attrs = {name: value if value is not None else "" for name, value in raw_attrs}
        if not self._is_interactive(tag, attrs):
            return
        record: dict[str, object] = {"tag": tag, "attrs": attrs, "text": ""}
        self._active.append(record)
        if tag == "input":
            self._finish(record)

    def handle_data(self, data: str) -> None:
        if self._active:
            self._active[-1]["text"] = str(self._active[-1]["text"]) + data

    def handle_endtag(self, tag: str) -> None:
        for record in reversed(self._active):
            if record["tag"] == tag:
                self._finish(record)
                break

    def _finish(self, record: dict[str, object]) -> None:
        if record not in self._active:
            return
        self._active.remove(record)
        attrs = dict(record["attrs"])
        text = " ".join(str(record["text"]).split())
        label = (
            attrs.get("aria-label")
            or attrs.get("title")
            or attrs.get("placeholder")
            or text
            or attrs.get("value")
            or str(record["tag"])
        )
        stable_id = _source_stable_id(self.surface, str(record["tag"]), attrs, label)
        match_attrs: dict[str, str] = {}
        if attrs.get("id"):
            match_attrs["id"] = attrs["id"]
        else:
            for name in (*[key for key in attrs if key.startswith("data-")], "role", "tabindex", "value"):
                if name in attrs:
                    match_attrs[name] = attrs[name]
        self.controls.append(
            {
                "surface": self.surface,
                "tag": record["tag"],
                "stable_id": stable_id,
                "label": label,
                "match_attrs": match_attrs,
                "text": text,
            }
        )


def _slug(value: str) -> str:
    output: list[str] = []
    separator = False
    for character in value.strip().lower():
        if character.isascii() and character.isalnum():
            output.append(character)
            separator = False
        elif output and not separator:
            output.append("-")
            separator = True
    return "".join(output).strip("-")[:80] or "unlabelled"


def _source_stable_id(surface: str, tag: str, attrs: dict[str, str], label: str) -> str:
    if attrs.get("id"):
        return f"{surface}:#{attrs['id']}"
    for name in _STABLE_DATA_ATTRIBUTES:
        if name in attrs:
            return f"{surface}:{name}={attrs[name]}"
    if "data-queue-refresh-button" in attrs:
        return f"{surface}:data-queue-refresh-button"
    if "data-ui-quick-link" in attrs:
        return f"{surface}:quick-link={_slug(label)}"
    if tag == "summary":
        return f"{surface}:summary={_slug(label)}"
    if tag == "button" and _slug(label) == "close":
        return f"{surface}:button=close"
    return f"{surface}:{tag}={_slug(label)}"


def _source_controls(repo_root: Path) -> list[dict[str, object]]:
    source_files = {
        "shell": repo_root / "apps" / "desktop" / "webview" / "static" / "partials" / "app-shell-start.html",
        "launch": repo_root / "apps" / "desktop" / "webview" / "static" / "partials" / "page-launch.html",
        "queue": repo_root / "apps" / "desktop" / "webview" / "static" / "partials" / "page-queue.html",
        "rename": repo_root / "apps" / "desktop" / "webview" / "static" / "partials" / "page-rename.html",
    }
    controls: list[dict[str, object]] = []
    for surface, path in source_files.items():
        parser = _SourceControlParser(surface)
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
        controls.extend(parser.controls)
    return controls


def _runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function censusScript() {
          return `
          (async () => {
            const fixture = window.__MEDIA_PIPELINE_CONTROL_CENSUS_FIXTURE;
            const expectedCounts = { shell: 32, launch: 38, queue: 99, rename: 39 };
            const nativeTags = new Set(["BUTTON", "INPUT", "SELECT", "TEXTAREA", "SUMMARY", "A"]);
            const posts = [];
            const confirmations = [];
            const failures = [];
            const activatedEvents = [];
            const generated = [];
            const shortcuts = [];
            const dedicatedCoverage = new Set(fixture.dedicatedCoverage || []);
            const skipped = new Map(Object.entries({
              "shell:data-control-action=kill": "SKIPPED — DESTRUCTIVE: emergency process-tree termination is not a read-only census action.",
              "launch:#pipeline-start-button": "SKIPPED — PROCESS MUTATION: starting a media pipeline is outside this control-only census.",
              "launch:data-control-action=pause": "SKIPPED — PROCESS MUTATION: pause/resume requires owned active work.",
              "launch:data-control-action=rescan": "SKIPPED — PROCESS MUTATION: rescan changes an active pipeline command flag.",
              "launch:data-control-action=stop": "SKIPPED — PROCESS MUTATION: stop-after-current requires owned active work.",
              "launch:data-control-action=kill": "SKIPPED — DESTRUCTIVE: force stop terminates an owned process tree.",
              "queue:#rerun-start-button": "SKIPPED — PROCESS MUTATION: CSV rerun start can launch media work.",
              "queue:#rerun-stop-after-current-button": "SKIPPED — PROCESS MUTATION: stop requires an owned active rerun.",
              "queue:#queue-priority-promote-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: covered by focused queue command tests, not this read-only census.",
              "queue:#queue-priority-normal-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: covered by focused queue command tests, not this read-only census.",
              "queue:#queue-priority-low-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: covered by focused queue command tests, not this read-only census.",
              "queue:#queue-priority-hold-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: covered by focused queue command tests, not this read-only census.",
              "queue:#queue-priority-promote-movies-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: bulk priority changes are outside this read-only census.",
              "queue:#queue-priority-promote-tv-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: bulk priority changes are outside this read-only census.",
              "queue:#queue-priority-clear-all-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: clears the priority manifest.",
              "queue:#queue-strategy-apply-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: saves queue strategy.",
              "queue:#queue-manual-save-order-btn": "SKIPPED — PERSISTENT QUEUE MUTATION: saves manual queue order.",
              "rename:#rename-log-case-submit-button": "SKIPPED — REPOSITORY MUTATION: appends a persistent bad-case corpus entry.",
            }));
            const explicitBlocked = new Map(Object.entries({
              "launch:#pipeline-start-mode": "BLOCKED — INTENTIONAL MIRROR: hidden select mirrors the visible mode buttons and is not user reachable.",
              "launch:#pipeline-single-file-browse-button": "BLOCKED — BACKEND INITIALIZATION STATE: the disposable facade reports initialization, so backend-owned browse remains disabled.",
              "launch:#pipeline-single-file-clear-button": "BLOCKED — BACKEND INITIALIZATION STATE: the disposable facade reports initialization, so staged-path clear remains disabled.",
              "queue:#rerun-open-csv-button": "BLOCKED — FIXTURE PRECONDITION: open requires a backend-known imported/scoped CSV key.",
              "queue:#rerun-open-csv-folder-button": "BLOCKED — FIXTURE PRECONDITION: open-folder requires a backend-known imported/scoped CSV key.",
              "queue:#rerun-scope-issue-filter": "BLOCKED — EMPTY BACKEND DIMENSION: no issue options exist in the disposable preview fixture.",
              "queue:#rerun-scope-bucket-filter": "BLOCKED — EMPTY BACKEND DIMENSION: no bucket options exist in the disposable preview fixture.",
              "queue:#queue-manual-discard-order-btn": "BLOCKED — SINGLE-ROW FIXTURE: no distinct manual-order draft can be created to discard.",
              "queue:#queue-page-prev-btn": "BLOCKED — SINGLE-PAGE FIXTURE: no previous 250-row page exists.",
              "queue:#queue-page-next-btn": "BLOCKED — SINGLE-PAGE FIXTURE: no next 250-row page exists.",
              "queue:data-fo-use-inherited=audioKeepLanguages": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits audio keep languages already.",
              "queue:data-fo-use-inherited=audioDropLanguages": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits audio drop languages already.",
              "queue:data-fo-use-inherited=audioPreferDefaultLanguage": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits preferred audio language already.",
              "queue:data-fo-use-inherited=subtitleStripAll": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits subtitle strip policy already.",
              "queue:data-fo-use-inherited=subtitleKeepLanguages": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits subtitle keep languages already.",
              "queue:data-fo-use-inherited=subtitleDropLanguages": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits subtitle drop languages already.",
              "queue:data-fo-use-inherited=routeProfile": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits route profile already.",
              "queue:data-fo-use-inherited=videoContainer": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits video container already.",
              "queue:data-fo-use-inherited=videoCodec": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits video codec already.",
              "queue:data-fo-use-inherited=videoEncodePreset": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits encode preset already.",
              "queue:data-fo-use-inherited=videoEncodeLadder": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits encode ladder already.",
              "queue:data-fo-use-inherited=routingRouteThresholdMode": "BLOCKED — NO SAVED EXACT OVERRIDE: the disposable row inherits route threshold mode already.",
              "queue:#fo-series-modal-close": "BLOCKED — SERIES PREVIEW PRECONDITION: this single-row backend fixture has no detectable series scope.",
              "queue:data-fo-series-filter=all": "BLOCKED — SERIES PREVIEW PRECONDITION: this single-row backend fixture has no detectable series scope.",
              "queue:data-fo-series-filter=will_update": "BLOCKED — SERIES PREVIEW PRECONDITION: this single-row backend fixture has no detectable series scope.",
              "queue:data-fo-series-filter=protected": "BLOCKED — SERIES PREVIEW PRECONDITION: this single-row backend fixture has no detectable series scope.",
              "queue:data-fo-series-filter=issues": "BLOCKED — SERIES PREVIEW PRECONDITION: this single-row backend fixture has no detectable series scope.",
              "rename:#rename-confirm-cancel-button": "BLOCKED — MUTATION DIALOG PRECONDITION: confirmation dialog opens only after Apply.",
              "rename:#rename-result-open-log-button": "BLOCKED — APPLY RESULT PRECONDITION: no real apply log is created in a non-mutating census.",
              "rename:button=close": "BLOCKED — APPLY RESULT PRECONDITION: result dialog opens only after Apply/Undo.",
            }));

            function byId(id) { return document.getElementById(id); }
            function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
            async function waitFor(predicate, label, timeoutMs = 10000) {
              const deadline = Date.now() + timeoutMs;
              let last = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  last = error;
                }
                await sleep(50);
              }
              throw new Error("Timed out waiting for " + label + (last ? ": " + last.message : ""));
            }
            function surfaceFor(node) {
              const page = node.closest?.("[data-page-panel]")?.dataset?.pagePanel || "";
              if (["launch", "queue", "rename"].includes(page)) return page;
              if (!page) return "shell";
              return "";
            }
            function slug(value) {
              return String(value || "")
                .trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "unlabelled";
            }
            function locateSourceControl(descriptor) {
              const root = descriptor.surface === "shell"
                ? document
                : document.querySelector('[data-page-panel="' + descriptor.surface + '"]');
              if (!root) return null;
              const id = descriptor.match_attrs?.id || "";
              if (id) return byId(id);
              const candidates = Array.from(root.querySelectorAll(descriptor.tag)).filter((node) => {
                if (surfaceFor(node) !== descriptor.surface) return false;
                const attrs = descriptor.match_attrs || {};
                if (!Object.entries(attrs).every(([name, value]) => node.hasAttribute(name) && node.getAttribute(name) === value)) return false;
                if (descriptor.text && !Object.keys(attrs).length) {
                  return String(node.textContent || "").trim().replace(/\\s+/g, " ") === descriptor.text;
                }
                return true;
              });
              return candidates[0] || null;
            }
            function staticInventory() {
              return (fixture.sourceControls || []).map((descriptor, ordinal) => {
                const node = locateSourceControl(descriptor);
                if (!node) throw new Error("source-authored control is missing at runtime: " + JSON.stringify(descriptor));
                return {
                  node,
                  surface: descriptor.surface,
                  stableId: descriptor.stable_id,
                  label: descriptor.label,
                  tag: descriptor.tag,
                  ordinal: ordinal + 1,
                };
              });
            }
            function isVisible(node) {
              if (!node || node.hidden || node.closest("[hidden]")) return false;
              const style = getComputedStyle(node);
              return style.display !== "none" && style.visibility !== "hidden"
                && Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            }
            function pageContext(item) {
              if (item.surface !== "shell") window.showPage(item.surface);
              const launchPanel = item.node.closest?.("[data-launch-tab-panel]")?.dataset?.launchTabPanel;
              if (launchPanel) window.mediaPipelineLaunchView?.activateLaunchTab?.(launchPanel, { persist: false });
              const queuePanel = item.node.closest?.("[data-queue-tab-panel]")?.dataset?.queueTabPanel;
              if (queuePanel) window.mediaPipelineQueueView?.activateQueueTab?.(queuePanel, { persist: false });
            }
            async function prepareControl(item) {
              pageContext(item);
              if (item.stableId.startsWith("queue:#queue-manual-move-")) {
                const strategy = byId("queue-strategy-select");
                strategy.value = "ManualOrder";
                dispatchInput(strategy);
                document.querySelector("#queue-rows tr[data-row-key]")?.click();
                window.mediaPipelineQueueView?.updateQueueManualOrderControls?.();
                await sleep(25);
              }
              if (item.node.closest?.("#fo-drawer") && byId("fo-drawer")?.hidden) {
                document.querySelector("#queue-rows .fo-open-btn")?.click();
                await waitFor(() => !byId("fo-drawer")?.hidden, "file override drawer", 2000);
              }
              if (item.node.closest?.("#fo-series-modal") && byId("fo-series-modal")?.hidden) {
                if (byId("fo-drawer")?.hidden) {
                  document.querySelector("#queue-rows .fo-open-btn")?.click();
                  await waitFor(() => !byId("fo-drawer")?.hidden, "file override drawer for series preview", 2000);
                }
                byId("fo-series-preview-open")?.click();
                await waitFor(() => !byId("fo-series-modal")?.hidden, "series preview modal", 2000);
              }
            }
            function dispatchInput(node) {
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function safeTextValue(node) {
              const values = {
                "pipeline-start-single-file": fixture.sourcePath,
                "rerun-start-csv-path": fixture.csvPath,
                "rename-add-path-input": fixture.sourcePath,
                "rename-paths": fixture.sourcePath,
                "rename-show": "Census Fixture",
                "rename-season": "S01",
                "rename-start": "E01",
                "rename-movie-year": "2026",
                "rename-log-case-source-folder": fixture.sourceFolder,
                "rename-log-case-source-file": fixture.sourcePath,
                "rename-log-case-expected-name": "Census Fixture - S01E01.mkv",
                "rename-log-case-expected-show": "Census Fixture",
                "rename-log-case-notes": "Disposable control census evidence only.",
                "queue-filter": "fixture",
              };
              if (Object.prototype.hasOwnProperty.call(values, node.id)) return values[node.id];
              if (node.type === "number") {
                const minimum = Number(node.min);
                return String(Number.isFinite(minimum) ? minimum : 1);
              }
              return node.value || "census";
            }
            async function activateNative(item) {
              const node = item.node;
              pageContext(item);
              if (item.tag === "input") {
                if (["checkbox", "radio"].includes(node.type)) {
                  const before = node.checked;
                  node.click();
                  if (node.checked === before && !node.disabled) throw new Error("checkbox/radio did not change");
                } else {
                  node.focus();
                  node.value = safeTextValue(node);
                  dispatchInput(node);
                }
              } else if (item.tag === "select") {
                if (!node.options.length) throw new Error("select has no options in this fixture");
                if (node.multiple) {
                  Array.from(node.options).forEach((option, index) => { option.selected = index === 0; });
                } else {
                  const options = Array.from(node.options).filter((option) => !option.disabled);
                  const current = options.findIndex((option) => option.value === node.value);
                  node.value = options[(current + 1 + options.length) % options.length]?.value ?? node.value;
                }
                dispatchInput(node);
              } else if (item.tag === "textarea") {
                node.focus();
                node.value = safeTextValue(node);
                dispatchInput(node);
              } else if (item.tag === "summary") {
                const details = node.closest("details");
                const before = Boolean(details?.open);
                node.click();
                if (details && details.open === before) throw new Error("details disclosure did not toggle");
              } else if (nativeTags.has(node.tagName)) {
                node.click();
              } else {
                node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
                node.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
              }
              activatedEvents.push(item.stableId);
              await sleep(35);
              if (item.stableId === "rename:#rename-preview-button") {
                await waitFor(() => document.querySelector('#rename-rows tr[data-selectable-row="true"]'), "rename preview row", 3000);
                document.querySelector('#rename-rows tr[data-selectable-row="true"]')?.click();
              }
            }

            const originalFetch = window.fetch.bind(window);
            window.confirm = (message) => {
              confirmations.push(String(message || ""));
              return false;
            };
            function responsePayload(path) {
              if (path === "/api/path-picker/browse") {
                return { ok: true, canceled: false, paths: [fixture.sourcePath], message: "Disposable fixture selected.", errors: [] };
              }
              if (path === "/api/rename/browse") {
                return { ok: true, paths: [fixture.sourcePath], message: "Disposable fixture selected.", warnings: [], errors: [] };
              }
              if (path === "/api/rename/preview") {
                const destination = fixture.sourceFolder + "/Census Fixture - S01E01.mkv";
                return {
                  ok: true,
                  command: "rename.preview",
                  rows: [{
                    source: fixture.sourcePath,
                    source_name: "Census Fixture S01E01.mkv",
                    source_parent: fixture.sourceFolder,
                    destination,
                    destination_parent: fixture.sourceFolder,
                    target_name: "Census Fixture - S01E01.mkv",
                    pipeline_guess: "Census Fixture - S01E01.mkv",
                    status: "ready",
                    confidence: "high",
                    preview_source: "census_fixture",
                    confidence_reasons: ["disposable fixture"],
                    change_kind: "rename",
                    sidecar_count: 0,
                    destination_exists: false,
                    matches_target: false,
                    warnings: [], errors: [],
                  }],
                  preview_fingerprint: "control-census-preview-fingerprint",
                  counts: { total: 1, ready: 1 },
                  confidence_counts: { high: 1 },
                  preview_source_counts: { census_fixture: 1 },
                  change_kind_counts: { rename: 1 },
                  warnings: [], errors: [],
                };
              }
              if (path.includes("file-overrides/series-preview")) {
                return { ok: true, command: "queue.file_overrides.series_preview", rows: [], counts: { total: 0 }, preview_fingerprint: "census-series" };
              }
              if (path.includes("file-overrides/series-clear-preview")) {
                return { ok: true, command: "queue.file_overrides.series_clear_preview", rows: [], counts: { total: 0 }, preview_fingerprint: "census-series-clear" };
              }
              if (path.includes("file-overrides/route-preview")) {
                return { ok: true, command: "queue.file_overrides.route_preview", route: "copy", route_reason: "Disposable census preview.", warnings: [] };
              }
              if (path === "/api/queue/open") return { ok: true, command: "queue.open", message: "Opened disposable fixture target." };
              if (path.includes("preview") || path.includes("dry-run") || path.includes("inspect")) {
                return { ok: true, command: "control.census.preview", message: "Disposable read-only preview complete.", rows: [], counts: {} };
              }
              return { ok: false, command: "control.census.blocked", message: "Control census intercepted non-read-only POST route." };
            }
            window.fetch = async (input, init = {}) => {
              const request = input instanceof Request ? input : null;
              const method = String(init.method || request?.method || "GET").toUpperCase();
              if (method !== "POST") return originalFetch(input, init);
              const rawUrl = String(request?.url || input || "");
              const url = new URL(rawUrl, window.location.href);
              let body = {};
              try { body = JSON.parse(String(init.body || "{}")); } catch (_) {}
              posts.push({ path: url.pathname, body });
              return new Response(JSON.stringify(responsePayload(url.pathname)), {
                status: 200,
                headers: { "Content-Type": "application/json" },
              });
            };

            await window.refreshAllNow({ page: "queue", reason: "control-census" });
            await waitFor(() => document.querySelector("#queue-rows tr[data-row-key]"), "queue fixture row");
            const inventory = staticInventory();
            const counts = Object.fromEntries(Object.keys(expectedCounts).map((surface) => [
              surface,
              inventory.filter((item) => item.surface === surface).length,
            ]));
            if (JSON.stringify(counts) !== JSON.stringify(expectedCounts)) {
              throw new Error("static control count drift: " + JSON.stringify({ counts, expectedCounts, ids: inventory.map((item) => item.stableId) }));
            }
            const ids = inventory.map((item) => item.stableId);
            if (new Set(ids).size !== ids.length) throw new Error("stable control IDs are not unique: " + JSON.stringify(ids));

            // Stage the Queue row and its generated file-override drawer control before
            // visiting drawer-owned static controls. This is a local, reversible UI action.
            window.showPage("queue");
            const queueRow = document.querySelector("#queue-rows tr[data-row-key]");
            queueRow?.click();
            const fileOverrideButton = queueRow?.querySelector(".fo-open-btn");
            if (fileOverrideButton) {
              fileOverrideButton.click();
              generated.push({ id: "queue:generated:file-overrides-open:first-row", outcome: "activated" });
              await sleep(100);
            }

            const results = [];
            for (const item of inventory) {
              const result = {
                stable_id: item.stableId,
                surface: item.surface,
                label: item.label,
                tag: item.tag,
                classification: "",
                reason: "",
                visible_before: false,
                enabled_before: !item.node.disabled,
              };
              pageContext(item);
              if (!dedicatedCoverage.has(item.stableId) && !skipped.has(item.stableId) && !explicitBlocked.has(item.stableId)) {
                try {
                  await prepareControl(item);
                } catch (error) {
                  result.classification = "failed";
                  result.reason = error?.message || String(error);
                  failures.push({ stable_id: item.stableId, error: result.reason });
                  results.push(result);
                  continue;
                }
              }
              result.visible_before = isVisible(item.node);
              if (dedicatedCoverage.has(item.stableId)) {
                result.classification = "activated";
                result.reason = "Activated through a dedicated disposable-browser flow in this test (mocked command boundary; no media mutation).";
              } else if (skipped.has(item.stableId)) {
                result.classification = "skipped";
                result.reason = skipped.get(item.stableId);
              } else if (explicitBlocked.has(item.stableId)) {
                result.classification = "blocked";
                result.reason = explicitBlocked.get(item.stableId);
              } else if (item.node.disabled) {
                result.classification = "blocked";
                result.reason = "BLOCKED — CURRENT FIXTURE STATE: the product rendered this otherwise safe control disabled.";
              } else {
                try {
                  await activateNative(item);
                  result.classification = "activated";
                  result.reason = "Physical browser event reached the production UI handler/local control path.";
                } catch (error) {
                  result.classification = "failed";
                  result.reason = error?.message || String(error);
                  failures.push({ stable_id: item.stableId, error: result.reason });
                }
              }
              results.push(result);
            }

            // Exercise generated data-table controls after the static flows have rendered
            // their fixture rows. Each instance receives its appropriate real browser event.
            function generatedSurface(node) {
              const page = node.closest?.("[data-page-panel]")?.dataset?.pagePanel || "";
              return ["launch", "queue", "rename"].includes(page) ? page : "";
            }
            function inGeneratedScope(node) {
              return ["launch", "queue", "rename"].includes(generatedSurface(node));
            }
            const tableSummaries = Array.from(document.querySelectorAll(".table-ui-toolbar .table-column-menu > summary")).filter(inGeneratedScope);
            tableSummaries.forEach((node, index) => {
              node.click();
              generated.push({ id: generatedSurface(node) + ":generated:columns:" + (node.closest(".table-ui-toolbar")?.dataset.tableToolbarFor || index), outcome: "activated" });
            });
            const columnCheckboxes = Array.from(document.querySelectorAll('.table-ui-toolbar input[type="checkbox"]')).filter(inGeneratedScope);
            columnCheckboxes.forEach((node, index) => {
              node.click();
              node.click();
              generated.push({ id: generatedSurface(node) + ":generated:column-visibility:" + slug(node.getAttribute("aria-label")) + ":" + index, outcome: "activated-restored" });
            });
            const sortButtons = Array.from(document.querySelectorAll(".table-sort-button")).filter(inGeneratedScope);
            sortButtons.forEach((node, index) => {
              node.click();
              node.click();
              generated.push({ id: generatedSurface(node) + ":generated:sort:" + slug(node.getAttribute("aria-label")) + ":" + index, outcome: "activated" });
            });
            const resizeButtons = Array.from(document.querySelectorAll(".table-column-resizer")).filter(inGeneratedScope);
            resizeButtons.forEach((node, index) => {
              node.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }));
              node.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true, cancelable: true }));
              generated.push({ id: generatedSurface(node) + ":generated:resize:" + slug(node.getAttribute("aria-label")) + ":" + index, outcome: "activated-restored" });
            });
            const selectableRows = [
              ...Array.from(document.querySelectorAll('[data-page-panel="queue"] tr[data-selectable-row="true"]')).map((node) => ({ node, surface: "queue" })),
              ...Array.from(document.querySelectorAll('[data-page-panel="rename"] tr[data-selectable-row="true"]')).map((node) => ({ node, surface: "rename" })),
            ];
            selectableRows.forEach(({ node, surface }, index) => {
              node.click();
              node.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
              node.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true }));
              generated.push({ id: surface + ":generated:selectable-row:" + slug(node.getAttribute("aria-label")) + ":" + index, outcome: "activated-click-enter-space" });
            });
            const renameChecks = Array.from(document.querySelectorAll('#rename-rows input[type="checkbox"]'));
            renameChecks.forEach((node, index) => {
              node.click();
              node.click();
              generated.push({ id: "rename:generated:row-check:" + index, outcome: "activated-restored" });
            });
            const queueOpenButtons = Array.from(document.querySelectorAll("[data-open-queue]"));
            for (let index = 0; index < queueOpenButtons.length; index += 1) {
              const node = queueOpenButtons[index];
              if (node.disabled) {
                generated.push({ id: "queue:generated:open:" + String(node.dataset.openTarget || index), outcome: "blocked-disabled" });
                continue;
              }
              node.click();
              generated.push({ id: "queue:generated:open:" + String(node.dataset.openTarget || index), outcome: "activated" });
              await sleep(30);
            }

            // Global shortcut registry: all 17 read-only shortcuts are exercised through
            // actual keydown events. Page-specific focus/row commands run from Queue.
            function sendShortcut(key) {
              const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
              document.body.dispatchEvent(event);
              shortcuts.push({ id: "shell:shortcut:" + key, prevented: event.defaultPrevented });
            }
            for (const key of ["1", "2", "3", "4", "5", "6", "7", "8", "9"]) sendShortcut(key);
            window.showPage("queue");
            window.mediaPipelineQueueView?.activateQueueTab?.("main", { persist: false });
            if (document.body.classList.contains("evidence-hidden")) byId("evidence-toggle")?.click();
            byId("queue-filter").value = "fixture";
            dispatchInput(byId("queue-filter"));
            for (const key of ["/", "c", "j", "k", "d", "a", "r", "?"]) {
              sendShortcut(key);
              await sleep(key === "r" ? 150 : 20);
            }
            if (shortcuts.length !== 17 || shortcuts.some((item) => !item.prevented)) {
              throw new Error("shortcut coverage failed: " + JSON.stringify(shortcuts));
            }

            // Tablist keyboard gestures are separate interaction paths from pointer clicks.
            window.showPage("launch");
            const launchTab = byId("launch-tab-pipeline");
            for (const key of ["ArrowRight", "ArrowLeft", "Home", "End"]) {
              launchTab.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
              generated.push({ id: "launch:gesture:tab:" + key, outcome: "activated" });
            }
            window.showPage("queue");
            const queueTab = byId("queue-tab-main");
            for (const key of ["ArrowRight", "ArrowLeft", "Home", "End"]) {
              queueTab.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
              generated.push({ id: "queue:gesture:tab:" + key, outcome: "activated" });
            }
            const renameAdd = byId("rename-add-path-input");
            renameAdd.value = fixture.sourcePath;
            renameAdd.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
            generated.push({ id: "rename:gesture:add-path:Enter", outcome: "activated" });

            const totals = {
              discovered: results.length,
              activated: results.filter((item) => item.classification === "activated").length,
              skipped: results.filter((item) => item.classification === "skipped").length,
              blocked: results.filter((item) => item.classification === "blocked").length,
              failed: results.filter((item) => item.classification === "failed").length,
              unclassified: results.filter((item) => !item.classification).length,
            };
            if (totals.discovered !== 208 || totals.unclassified !== 0 || totals.failed !== 0) {
              throw new Error("census totals failed: " + JSON.stringify({ totals, failures, results }));
            }
            return {
              ok: true,
              counts,
              totals,
              results,
              generated,
              generatedTotals: {
                discovered: generated.length,
                activated: generated.filter((item) => item.outcome.startsWith("activated")).length,
                blocked: generated.filter((item) => item.outcome.startsWith("blocked")).length,
              },
              shortcuts,
              posts,
              confirmations,
              activatedEventCount: activatedEvents.length,
            };
          })()
          `;
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new", "--disable-gpu", "--disable-background-networking", "--disable-default-apps",
            "--disable-extensions", "--disable-sync", "--metrics-recording-only", "--no-first-run",
            "--no-default-browser-check", `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`, payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              try {
                const ready = await client.send("Runtime.evaluate", {
                  expression: `Boolean(document.readyState === "complete" && typeof window.showPage === "function" && typeof window.refreshAllNow === "function" && document.getElementById("pipeline-start-button") && document.getElementById("queue-filter") && document.getElementById("rename-preview-button"))`,
                  returnByValue: true,
                });
                if (ready.result?.value === true) break;
              } catch (error) {
                if (!String(error?.message || error).includes("Execution context was destroyed")) throw error;
              }
              await sleep(100);
            }
            await client.send("Runtime.evaluate", {
              expression: `window.__MEDIA_PIPELINE_CONTROL_CENSUS_FIXTURE = ${JSON.stringify(payload.fixture)}`,
              returnByValue: true,
            });
            const evaluation = await client.send("Runtime.evaluate", {
              expression: censusScript(), awaitPromise: true, returnByValue: true,
            });
            if (evaluation.exceptionDetails) {
              const details = evaluation.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            if (client.exceptions.length) throw new Error(client.exceptions.join("; "));
            console.log(JSON.stringify({ ok: true, result: evaluation.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }
        main().catch((error) => { console.error(error.stack || error.message || String(error)); process.exit(1); });
        """
    )


class WebViewBrowserShellLaunchQueueRenameControlCensus(unittest.TestCase):
    def test_backend_served_control_census_is_complete_and_non_mutating(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser control census.")
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the browser control census.")

        with tempfile.TemporaryDirectory() as raw_root, tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
            root = Path(raw_root)
            tmp = Path(raw_tmp)
            source_controls = _source_controls(find_repo_root(Path(__file__)))
            source_counts = {
                surface: sum(control["surface"] == surface for control in source_controls)
                for surface in EXPECTED_STATIC_COUNTS
            }
            self.assertEqual(source_counts, EXPECTED_STATIC_COUNTS)
            self.assertEqual(len(source_controls), 208)
            self.assertEqual(len({control["stable_id"] for control in source_controls}), 208)
            resolved, source, output = _write_fixture_state(root)
            csv_path = root / "State" / "Imports" / "control-census.csv"
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            csv_path.write_text("source_path,status\n" + str(source) + ",ready\n", encoding="utf-8")
            media_snapshot = capture_media_no_mutation_snapshot(root)
            source_bytes = source.read_bytes()
            output_bytes = output.read_bytes()

            service = DummyWorkflowFacadeService(root)
            repo_root = find_repo_root(Path(__file__))
            service.workspace_root = repo_root
            resolved.powershell_host = str(
                repo_root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-shell-launch-queue-rename-control-census-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            payload_path = tmp / "control-census-payload.json"
            runner_path = tmp / "control-census-runner.cjs"
            runner_path.write_text(_runner_source(), encoding="utf-8")
            try:
                server.start()
                queue_override_result = _run_browser_queue_file_overrides_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                )
                rename_result = _run_browser_rename_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                )
                payload_path.write_text(
                    json.dumps(
                        {
                            "browserPath": browser_path,
                            "port": free_port(),
                            "tmpRoot": str(tmp),
                            "url": f"{server.url}/",
                            "fixture": {
                                "sourcePath": str(source),
                                "sourceFolder": str(source.parent),
                                "csvPath": str(csv_path),
                                "sourceControls": source_controls,
                                "dedicatedCoverage": [
                                    "queue:#fo-drawer-save",
                                    "queue:#fo-remux-pilot-promote",
                                    "queue:#fo-drawer-clear",
                                    "queue:data-fo-use-inherited=audioMaxChannels",
                                    "queue:#fo-series-preview-open",
                                    "queue:#fo-series-clear-open",
                                    "queue:#fo-series-apply",
                                    "queue:#fo-series-cancel",
                                    "rename:#rename-clear-paths-button",
                                    "rename:#rename-apply-button",
                                    "rename:#rename-undo-button",
                                    "rename:#rename-confirm-apply-button",
                                ],
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                result = run_node_browser_smoke(
                    "Browser-backed Shell/Launch/Queue/Rename control census",
                    node=node,
                    runner_path=runner_path,
                    payload_path=payload_path,
                    timeout_seconds=120,
                )
            finally:
                server.stop()

            assert_media_no_mutation(self, media_snapshot)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(output.read_bytes(), output_bytes)

        self.assertTrue(queue_override_result["ok"])
        self.assertTrue(rename_result["ok"])
        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["counts"], EXPECTED_STATIC_COUNTS)
        stable_totals = {
            key: value
            for key, value in browser_result["totals"].items()
            if key not in {"activated", "blocked"}
        }
        self.assertEqual(stable_totals, EXPECTED_CLASSIFICATION_TOTALS)
        self.assertIn(
            (
                browser_result["totals"]["activated"],
                browser_result["totals"]["blocked"],
            ),
            EXPECTED_CLASSIFICATION_SPLITS,
        )
        self.assertEqual(len(browser_result["results"]), 208)
        self.assertEqual(len({item["stable_id"] for item in browser_result["results"]}), 208)
        self.assertEqual(len(browser_result["shortcuts"]), 17)
        self.assertEqual(browser_result["generatedTotals"], EXPECTED_GENERATED_TOTALS)

        print(
            "CONTROL_CENSUS_JSON="
            + json.dumps(
                {
                    "counts": browser_result["counts"],
                    "totals": browser_result["totals"],
                    "generated_totals": browser_result["generatedTotals"],
                    "stable_ids": [item["stable_id"] for item in browser_result["results"]],
                    "controls": [
                        {
                            "stable_id": item["stable_id"],
                            "classification": item["classification"],
                            "reason": item["reason"],
                        }
                        for item in browser_result["results"]
                    ],
                    "generated": browser_result["generated"],
                    "shortcuts": browser_result["shortcuts"],
                    "post_paths": [post["path"] for post in browser_result["posts"]],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
