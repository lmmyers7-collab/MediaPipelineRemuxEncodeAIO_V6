from __future__ import annotations

import csv
from datetime import datetime, timedelta
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.core.api.commands_process import LocalApiProcessCommandPayloadMixin
from mediapipeline.desktop.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
from mediapipeline.desktop.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT
from mediapipeline.desktop.api.handler import build_local_api_handler_class
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend
from mediapipeline.desktop.models import ResolvedPaths, Snapshot
from tests.css_import_resolver import resolve_css_imports, resolved_css_asset_bundle
from tests.python.desktop.application_facade_test_support import (
    DummyFacadeService,
    DummyProc,
    DummyWorkflowFacadeService,
    assert_namespace_export as _assert_namespace_export,
    _read_command_history_asset_bundle,
    _read_completed_asset_bundle,
    _read_completed_evidence_asset_bundle,
    _read_completed_review_asset_bundle,
    _read_diagnostics_asset_bundle,
    _read_dom_helpers_asset_bundle,
    _read_launch_risk_asset_bundle,
    _read_launch_view_asset_bundle,
    _read_pending_publish_asset_bundle,
    _read_queue_asset_bundle,
    _read_queue_file_overrides_asset_bundle,
    _read_rename_asset_bundle,
    _read_settings_asset_bundle,
    _render_static_index_html,
    _resolved,
)


def _read_components_css(assets_root: Path) -> str:
    return resolve_css_imports(assets_root / "styles.components.css", assets_root)


def _read_queue_css(assets_root: Path) -> str:
    return resolve_css_imports(assets_root / "styles.queue.css", assets_root)


NETWORK_ASSET_NAMES = (
    "network/configDiagnostics.js",
    "network/config.js",
    "network/queueProjection.js",
    "network/overviewTiles.js",
    "network/overviewModel.js",
    "network/lifecycleContract.js",
    "network/stateFiles.js",
    "network/readiness.js",
    "network/lifecycle.view.js",
    "network/status.js",
    "network/lifecycle.model.js",
    "network/lifecycle.results.js",
    "network/lifecycle.commands.js",
    "network/setup.commands.js",
    "network/settingsHandoff.js",
    "network/openHistory.js",
    "network/evidence.js",
    "network/workers.model.js",
    "network/workers.view.js",
    "network/roleDashboard.js",
    "network/rerunEvidence.js",
    "network/events.js",
    "networkView.js",
)


def _read_network_asset_bundle(assets_root: Path) -> str:
    parts: list[str] = []
    for name in NETWORK_ASSET_NAMES:
        path = assets_root / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    if not parts or "window.mediaPipelineNetworkView" not in parts[-1]:
        raise AssertionError("networkView.js must remain the public Network facade")
    return "\n".join(parts)


class ApplicationFacadeWebStaticTests(unittest.TestCase):
    def test_sidebar_nav_order_and_output_publish_tab(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        shell_html = (static_root / "partials" / "app-shell-start.html").read_text(encoding="utf-8")
        completed_html = (static_root / "partials" / "page-completed.html").read_text(encoding="utf-8")
        pending_html = (static_root / "partials" / "page-pending.html").read_text(encoding="utf-8")

        ordered_pages = [
            "home",
            "launch",
            "live",
            "metrics",
            "queue",
            "completed",
            "pending",
            "rename",
            "reports",
            "network",
            "libraries",
            "schedule",
            "settings",
            "diagnostics",
            "maintenance",
        ]
        positions = [shell_html.index(f'data-page="{page}"') for page in ordered_pages]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('data-page="pending"', shell_html)

        completed_tab_order = [
            'data-completed-tab="overview"',
            'data-completed-tab="history"',
            'data-completed-tab="evidence"',
        ]
        completed_positions = [completed_html.index(token) for token in completed_tab_order]
        self.assertEqual(completed_positions, sorted(completed_positions))
        pending_tab_order = [
            "Pending Publish Operations",
            "Live Run",
            "File Inventory",
            "Pending Publish Guard Evidence",
        ]
        pending_positions = [pending_html.index(token) for token in pending_tab_order]
        self.assertEqual(pending_positions, sorted(pending_positions))
        self.assertIn('data-page-panel="pending"', pending_html)
        self.assertIn("pending-action-drain-button", pending_html)
        self.assertIn("pending-drain-button", pending_html)

    def test_pending_publish_action_center_static_contract(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        assets_root = static_root / "assets"
        pending_html = (static_root / "partials" / "page-pending.html").read_text(encoding="utf-8")
        pending_publish_view_js = _read_pending_publish_asset_bundle(assets_root)
        pending_publish_filters_js = (assets_root / "pendingPublish" / "filters.js").read_text(encoding="utf-8")
        styles_css = _read_components_css(assets_root)

        self.assertIn("<h2>Pending Publish Operations</h2>", pending_html)
        self.assertIn('id="pending-action-drain-button"', pending_html)
        self.assertIn('id="pending-action-refresh-button"', pending_html)
        self.assertIn('id="pending-action-failed-count"', pending_html)
        self.assertIn('id="pending-action-drained-count"', pending_html)
        self.assertIn('data-pending-action-filter="blocked"', pending_html)
        self.assertIn('data-pending-action-filter="failed"', pending_html)
        self.assertIn('data-pending-action-filter="drained"', pending_html)
        self.assertIn('<option value="evidence_missing">Evidence missing</option>', pending_html)
        self.assertIn('<option value="failed">Failed</option>', pending_html)
        self.assertIn('<option value="drained">Drained</option>', pending_html)
        self.assertEqual(pending_html.count('id="pending-drain-button"'), 1)
        self.assertLess(
            pending_html.index("Pending Publish Operations"),
            pending_html.index("Pending Publish Guard Evidence"),
        )
        self.assertIn("function renderPendingActionCenter", pending_publish_view_js)
        self.assertIn("function applyPendingActionFilter", pending_publish_view_js)
        self.assertIn("Boundary: this action center can only update local filters", pending_publish_view_js)
        self.assertIn("drainButton.click();", pending_publish_view_js)
        self.assertIn("evidence_missing", pending_publish_filters_js)
        self.assertIn(".pending-action-filter", styles_css)
        _assert_namespace_export(self, pending_publish_view_js, "mediaPipelinePendingPublishView", "renderPendingActionCenter")

    def test_topbar_event_ticker_formats_pending_and_backend_events(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the WebView lifecycle ticker static smoke.")
        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const lifecycleAssetPaths = [
              "apps/desktop/webview/static/assets/app/lifecycle/topbar.js",
              "apps/desktop/webview/static/assets/app/lifecycle/navigation.js",
              "apps/desktop/webview/static/assets/app/lifecycle.js",
            ].map((assetPath) => path.join(process.cwd(), assetPath));
            const lifecyclePath = lifecycleAssetPaths.at(-1);
            const source = lifecycleAssetPaths
              .map((assetPath) => fs.readFileSync(assetPath, "utf8"))
              .join("\n");
            const ticker = { textContent: "", title: "", dataset: {} };
            const activity = {
              textContent: "",
              title: "",
              replaceChildren(...children) {
                this.children = children;
                this.textContent = children.map((child) => child.textContent || "").join(" ");
              },
            };
            const context = {
              window: {},
              console,
              document: {
                createElement() {
                  return { className: "", textContent: "", title: "", dataset: {} };
                },
              },
              Date,
              setTimeout,
              clearTimeout,
              lastSnapshot: { pipeline_state: "processing", recent_events: [] },
              byId(id) {
                if (id === "topbar-event-ticker") return ticker;
                if (id === "activity") return activity;
                return null;
              },
              mediaPipelineFormatters: { formatProgressValue(value) { return value == null ? "" : String(value); } },
              homeProgressPercent(value) { return value == null || value === "" ? "" : `${value}%`; },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: lifecyclePath });
            const lifecycle = context.window.mediaPipelineAppLifecycle;
            if (!lifecycle?.renderTopbarEventTicker || !lifecycle?.setTopbarPendingLaunch) {
              throw new Error("Ticker lifecycle exports are missing");
            }

            lifecycle.renderTopbarEventTicker({ pipeline_state: "idle", recent_events: [] });
            if (ticker.dataset.state !== "empty" || !ticker.textContent.includes("no backend pipeline events")) {
              throw new Error(`Unexpected empty ticker: ${ticker.dataset.state} ${ticker.textContent}`);
            }

            lifecycle.setTopbarPendingLaunch({ pid: "20676" });
            if (
              ticker.dataset.state !== "pending"
              || !ticker.textContent.includes("pipeline.start accepted")
              || !ticker.textContent.includes("PID 20676")
            ) {
              throw new Error(`Unexpected pending ticker: ${ticker.dataset.state} ${ticker.textContent}`);
            }

            lifecycle.setTopbarPendingLaunch({
              label: "CSV rerun",
              status_label: "submitted",
              wait_label: "waiting for backend response",
            });
            if (
              ticker.dataset.state !== "pending"
              || !ticker.textContent.includes("CSV rerun submitted")
              || !ticker.textContent.includes("waiting for backend response")
            ) {
              throw new Error(`Unexpected CSV rerun pending ticker: ${ticker.dataset.state} ${ticker.textContent}`);
            }
            lifecycle.renderTopbarActivity({ pipeline_state: "idle", activity: "None", recent_events: [] });
            if (!activity.textContent.includes("CSV rerun submitted")) {
              throw new Error(`Pending CSV rerun activity was overwritten: ${activity.textContent}`);
            }
            if (!lifecycle.clearTopbarPendingLaunch) {
              throw new Error("clearTopbarPendingLaunch export is missing");
            }
            lifecycle.clearTopbarPendingLaunch({ pipeline_state: "idle", recent_events: [] });
            if (ticker.dataset.state !== "empty" || !ticker.textContent.includes("no backend pipeline events")) {
              throw new Error(`Unexpected cleared ticker: ${ticker.dataset.state} ${ticker.textContent}`);
            }

            lifecycle.renderTopbarEventTicker({
              pipeline_state: "processing",
              recent_events: [
                {
                  event_type: "job_started",
                  timestamp: "2026-06-02T10:00:02Z",
                  stage: "processing",
                  status: "active",
                  data: { source_path: "C:/Movies/The Hobbit The Desolation of Smaug 2013 Extended.mkv" },
                },
                { event_type: "queue_scan_started", timestamp: "2026-06-02T10:00:00Z", status: "started" },
              ],
            });
            if (
              ticker.dataset.state !== "event"
              || !ticker.textContent.includes("job_started")
              || !ticker.textContent.includes("The Hobbit")
            ) {
              throw new Error(`Unexpected event ticker: ${ticker.dataset.state} ${ticker.textContent}`);
            }

            const formatted = lifecycle.topbarEventTickerLine({
              event_type: "very_long_event_name_that_should_still_render",
              data: { source_path: `C:/Movies/${"A".repeat(180)}.mkv` },
            });
            if (!formatted.includes("Latest event:") || formatted.length > 180) {
              throw new Error(`Unexpected formatted ticker length/text: ${formatted.length} ${formatted}`);
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_progress_bar_updated_at_uses_date_then_time(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the progress timestamp formatter smoke.")
        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const progressPath = path.join(
              process.cwd(),
              "apps/desktop/webview/static/assets/progressView.js"
            );
            const source = [
              "progress/barState.js", "progress/barPresentation.js", "progress/audit.js",
              "progress/details.js", "progress/evidenceRows.js", "progress/worker.js",
              "progress/ffmpegEta.js", "progress/diagnostics.js", "progress/evidence.js",
              "progress/activeWork.js", "progress/csvRerun.js", "progress/timelineCore.js",
              "progress/liveRun.js", "progress/timelineView.js", "progressView.js",
            ].map((name) => fs.readFileSync(path.join(process.cwd(), "apps/desktop/webview/static/assets", name), "utf8")).join("\n");
            const progressChildren = ["barState.js", "barPresentation.js", "audit.js", "details.js", "worker.js", "csvRerun.js", "ffmpegEta.js", "activeWork.js", "diagnostics.js", "evidence.js", "evidenceRows.js", "timelineCore.js", "liveRun.js", "timelineView.js"].map((name) => {
              const childPath = path.join(process.cwd(), "apps/desktop/webview/static/assets/progress", name);
              return { childPath, source: fs.readFileSync(childPath, "utf8") };
            });
            function makeElement(tag) {
              const node = {
                tagName: String(tag || "").toUpperCase(),
                children: [],
                dataset: {},
                className: "",
                style: {},
                attributes: {},
                appendChild(child) {
                  this.children.push(child);
                  return child;
                },
                append(...items) { items.forEach((item) => this.appendChild(item)); },
                replaceChildren(...items) { this.children = []; this.append(...items); },
                setAttribute(name, value) { this.attributes[name] = String(value); },
                _textContent: "",
              };
              Object.defineProperty(node, "textContent", {
                get() {
                  return this._textContent || this.children.map((child) => child.textContent || "").join("");
                },
                set(value) {
                  this._textContent = String(value ?? "");
                  this.children = [];
                },
              });
              return node;
            }
            const container = makeElement("div");
            const context = {
              window: {},
              console,
              Date,
              document: { createElement: makeElement },
              byId() { return null; },
              setText() {},
              clearRows() {},
              updateTableStatusLegend() {},
              appendCells() {},
              makeRowSelectable() {},
              mediaPipelineFormatters: { formatProgressValue(value) { return value == null ? "" : String(value); } },
            };
            context.window = context;
            vm.createContext(context);
            progressChildren.forEach(({ childPath, source }) => vm.runInContext(source, context, { filename: childPath }));
            vm.runInContext(source, context, { filename: progressPath });
            const progress = context.window.mediaPipelineProgressView;
            if (!progress?.renderProgressBarsInto || !progress?.formatProgressUpdatedAt) {
              throw new Error("Progress renderer exports are missing");
            }
            if (progress.formatProgressUpdatedAt("2026-05-22T19:42:39.4749504Z") !== "2026-05-22 19:42:39") {
              throw new Error("Fractional UTC timestamp was not normalized");
            }

            progress.renderProgressBarsInto(container, [
              {
                label: "Audit progress",
                status: "complete",
                percent: 100,
                detail: "2507 / 2507 | Audit complete.",
                source: "audit_progress.json",
                updated_at: "2026-05-22T19:42:39.4749504Z",
              },
              {
                label: "Current backend stage",
                status: "idle",
                detail: "idle | None",
                source: "pipeline_progress.json",
                updated_at: "2026-06-03 22:00:04",
              },
            ]);
            const details = container.children.map((row) => row.children[2]?.textContent || "");
            if (!details[0].includes("updated: 2026-05-22 19:42:39")) {
              throw new Error(`Audit updated timestamp was not normalized: ${details[0]}`);
            }
            if (!details[1].includes("updated: 2026-06-03 22:00:04")) {
              throw new Error(`Existing date/time timestamp changed unexpectedly: ${details[1]}`);
            }
            const rendered = details.join("\n");
            if (rendered.includes(".4749504") || rendered.includes("T19:42") || rendered.includes("39Z")) {
              throw new Error(`Raw ISO timestamp leaked into progress detail: ${rendered}`);
            }
            progress.renderProgressBarsInto(container, [
              {
                id: "publish_output",
                label: "Publish steps",
                status: "active",
                mode: "stepped",
                percent: 0,
                steps: [
                  { id: "copy", label: "Copy completed output", status: "active" },
                  { id: "sidecars", label: "Write sidecars", status: "pending" },
                ],
              },
              {
                id: "publish_copy",
                label: "Publishing completed output",
                status: "active",
                percent: 50,
                detail: "512.0 MB / 1.0 GB",
                source: "pipeline_progress.json",
              },
            ], {
              eta: {
                rows: [
                  {
                    worker_id: "publish_copy",
                    worker_label: "Publishing completed output",
                    eta_seconds: 60,
                    bytes_per_second: 8947849,
                    bytes_remaining: 536870912,
                    confidence: "medium",
                    progress_source: "pipeline_progress.json",
                  },
                ],
              },
            });
            const stepList = container.children[0]?.children[2];
            const stepText = stepList?.children.map((child) => child.textContent).join(" | ") || "";
            if (!stepText.includes("Copy completed output") || !stepText.includes("Write sidecars")) {
              throw new Error(`Publish steps did not render: ${stepText}`);
            }
            const pushDetail = container.children[1]?.children[2]?.textContent || "";
            if (!pushDetail.includes("eta 1m 00s") || !pushDetail.includes("write 8.5 MB/s") || !pushDetail.includes("remaining 512.0 MB")) {
              throw new Error(`Push ETA detail did not render: ${pushDetail}`);
            }
            progress.renderProgressBarsInto(container, [
              {
                id: "publish_output",
                label: "Publish steps",
                status: "active",
                mode: "stepped",
                percent: 0,
                detail: "0 / 4 publish steps | copying | csv_rerun | Paprika (2006).rerun_20260704_231853_ef58146f.mkv",
                steps: [
                  { id: "copy", label: "Copy completed output", status: "active" },
                  { id: "sidecars", label: "Write sidecars", status: "pending" },
                ],
                source: "pipeline_progress.json",
                updated_at: "2026-07-05T16:05:41Z",
              },
              {
                id: "publish_copy",
                label: "Publishing completed output",
                status: "active",
                percent: 15.1,
                detail: "814.0 MB / 5.3 GB | csv_rerun | Paprika (2006).rerun_20260704_231853_ef58146f.mkv",
                source: "pipeline_progress.json",
                updated_at: "2026-07-05T16:05:41Z",
              },
              {
                id: "pending_drain",
                label: "Pending publish drain",
                status: "active",
                percent: 3.4,
                detail: "3 / 89 manifests | succeeded 2 | remaining 86 | Paprika (2006).rerun_20260704_231853_ef58146f.manifest.json",
                source: "pipeline_progress.json",
                updated_at: "2026-07-05T16:05:15Z",
              },
            ], {
              eta: {
                rows: [
                  {
                    worker_id: "publish_copy",
                    eta_seconds: 157,
                    bytes_remaining: 4831838208,
                    confidence: "low",
                    progress_source: "pipeline_progress.json",
                  },
                ],
              },
            }, "No active pending-publish drain progress loaded.", { compact: "pendingDrain" });
            const compactText = container.textContent;
            for (const fragment of [
              "Publish",
              "Copy output",
              "Drain queue",
              "0 of 4 steps",
              "Copy output",
              "Sidecars",
              "814.0 MB of 5.3 GB",
              "ETA 2m 37s",
              "4.5 GB left",
              "3 of 89 manifests",
              "2 done",
              "86 left",
            ]) {
              if (!compactText.includes(fragment)) {
                throw new Error(`Compact pending drain progress missing ${fragment}: ${compactText}`);
              }
            }
            for (const forbidden of ["Publishing completed output", "Publish steps", "source:", "updated:", "confidence:", "csv_rerun"]) {
              if (compactText.includes(forbidden)) {
                throw new Error(`Compact pending drain progress kept noisy text ${forbidden}: ${compactText}`);
              }
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_home_progress_stale_review_requires_consecutive_snapshots(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the progress stale hysteresis smoke.")
        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const progressPath = path.join(
              process.cwd(),
              "apps/desktop/webview/static/assets/progressView.js"
            );
            const source = [
              "progress/barState.js", "progress/barPresentation.js", "progress/audit.js",
              "progress/details.js", "progress/evidenceRows.js", "progress/worker.js",
              "progress/ffmpegEta.js", "progress/diagnostics.js", "progress/evidence.js",
              "progress/activeWork.js", "progress/csvRerun.js", "progress/timelineCore.js",
              "progress/liveRun.js", "progress/timelineView.js", "progressView.js",
            ].map((name) => fs.readFileSync(path.join(process.cwd(), "apps/desktop/webview/static/assets", name), "utf8")).join("\n");
            function makeElement(tag) {
              const node = {
                tagName: String(tag || "").toUpperCase(),
                children: [],
                dataset: {},
                className: "",
                style: {},
                attributes: {},
                title: "",
                appendChild(child) {
                  this.children.push(child);
                  return child;
                },
                append(...items) { items.forEach((item) => this.appendChild(item)); },
                replaceChildren(...items) { this.children = []; this.append(...items); },
                setAttribute(name, value) { this.attributes[name] = String(value); },
                classList: {
                  values: new Set(),
                  add(...names) { names.forEach((name) => this.values.add(name)); },
                  remove(...names) { names.forEach((name) => this.values.delete(name)); },
                  contains(name) { return this.values.has(name); },
                },
                _textContent: "",
              };
              Object.defineProperty(node, "textContent", {
                get() {
                  return this._textContent || this.children.map((child) => child.textContent || "").join("");
                },
                set(value) {
                  this._textContent = String(value ?? "");
                  this.children = [];
                },
              });
              return node;
            }
            const container = makeElement("div");
            const context = {
              window: {},
              console,
              Date,
              document: { createElement: makeElement },
              byId(id) { return id === "progress-bar-list" ? container : null; },
              clearRows(node) { if (node) node.textContent = ""; },
              appendCells() {},
              makeRowSelectable() {},
              setText() {},
              updateTableStatusLegend() {},
              mediaPipelineFormatters: { formatProgressValue(value) { return value == null ? "" : String(value); } },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: progressPath });
            const progress = context.window.mediaPipelineProgressView;
            if (!progress?.renderProgressBars) {
              throw new Error("Progress renderer export is missing");
            }

            function text() {
              return container.textContent;
            }
            function rowStatuses(node = container, statuses = []) {
              if (node.dataset?.status) statuses.push(node.dataset.status);
              (node.children || []).forEach((child) => rowStatuses(child, statuses));
              return statuses;
            }
            function snapshotFor(file) {
              return {
                progress: {
                  CurrentFileDisplay: file,
                  CurrentQueueIndex: 1,
                  CurrentQueueTotal: 2,
                },
              };
            }
            function staleBar(file) {
              return {
                id: "publish_copy",
                label: "Publishing completed output",
                status: "warning",
                percent: 72,
                detail: `copying | ${file}`,
                source: "pipeline_progress.json",
                updated_at: "2026-06-07 14:03:42",
                stale: true,
              };
            }
            function freshBar(file) {
              return {
                ...staleBar(file),
                status: "active",
                stale: false,
              };
            }

            progress.renderProgressBars([staleBar("Movie A.mkv")], snapshotFor("Movie A.mkv"));
            if (text().includes("stale/review")) {
              throw new Error(`First stale snapshot rendered stale token: ${text()}`);
            }
            if (rowStatuses().includes("warning")) {
              throw new Error(`First stale snapshot kept stale-derived warning status: ${rowStatuses().join(",")}`);
            }

            progress.renderProgressBars([staleBar("Movie A.mkv")], snapshotFor("Movie A.mkv"));
            if (!text().includes("stale/review")) {
              throw new Error(`Second stale snapshot did not render stale token: ${text()}`);
            }

            progress.renderProgressBars([staleBar("Movie B.mkv")], snapshotFor("Movie B.mkv"));
            if (text().includes("stale/review")) {
              throw new Error(`File change did not reset stale confirmation: ${text()}`);
            }

            progress.renderProgressBars([staleBar("Movie B.mkv")], snapshotFor("Movie B.mkv"));
            if (!text().includes("stale/review")) {
              throw new Error(`Second stale snapshot for changed file did not render stale token: ${text()}`);
            }

            progress.renderProgressBars([freshBar("Movie B.mkv")], snapshotFor("Movie B.mkv"));
            if (text().includes("stale/review")) {
              throw new Error(`Fresh snapshot did not clear stale token: ${text()}`);
            }

            progress.renderProgressBars([staleBar("Movie B.mkv")], snapshotFor("Movie B.mkv"));
            if (text().includes("stale/review")) {
              throw new Error(`Fresh snapshot did not reset stale confirmation count: ${text()}`);
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_home_recent_completed_prefers_episode_identity_for_tv_rows(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the Home recent-completed formatter smoke.")
        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const homePath = path.join(
              process.cwd(),
              "apps/desktop/webview/static/assets/app/home.js"
            );
            const source = [
              "apps/desktop/webview/static/assets/app/home/dailyDriver.js",
              "apps/desktop/webview/static/assets/app/home/queueProjection.js",
              "apps/desktop/webview/static/assets/app/home.js",
            ].map((name) => fs.readFileSync(path.join(process.cwd(), name), "utf8")).join("\n");
            function makeElement(tag) {
              const node = {
                tagName: String(tag || "").toUpperCase(),
                children: [],
                cells: [],
                title: "",
                dataset: {},
                className: "",
                classList: { add(value) { node.className = [node.className, value].filter(Boolean).join(" "); } },
                appendChild(child) {
                  this.children.push(child);
                  if (this.tagName === "TR" && child.tagName === "TD") this.cells.push(child);
                  return child;
                },
                append(...items) { items.forEach((item) => this.appendChild(item)); },
                _textContent: "",
              };
              Object.defineProperty(node, "textContent", {
                get() {
                  return this._textContent || this.children.map((child) => child.textContent || "").join("");
                },
                set(value) {
                  this._textContent = String(value ?? "");
                  if (this.tagName === "TBODY") this.children = [];
                },
              });
              Object.defineProperty(node, "innerText", {
                get() { return this.textContent; },
                set(value) { this.textContent = value; },
              });
              return node;
            }
            const elements = {
              "home-recent-completed-tbody": makeElement("tbody"),
              "home-recent-completed-status": makeElement("strong"),
            };
            const context = {
              window: {},
              console,
              document: { createElement: makeElement },
              byId(id) { return elements[id] || null; },
              clearRows(node) { if (node) node.textContent = ""; },
              makeRowSelectable() {},
              appendCells(row, values) {
                values.forEach((value) => {
                  const cell = makeElement("td");
                  cell.textContent = value;
                  row.appendChild(cell);
                });
              },
              setText(id, value) { if (elements[id]) elements[id].textContent = value; },
              mediaPipelineFormatters: { formatProgressValue(value) { return value == null ? "" : String(value); } },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: homePath });
            const home = context.window.mediaPipelineAppHome;
            if (!home?.renderHomeRecentCompleted) {
              throw new Error("Home recent-completed renderer export is missing");
            }

            home.renderHomeRecentCompleted({
              count: 2,
              rows: [
                {
                  media_type: "TV",
                  lookup_title: "TV (Season 02)",
                  output_file: "TV (Season 02).mkv",
                  output_path: "D:/Outsource/TV/TV/Season 02/TV (Season 02).mkv",
                  source_path: "D:/Source/Anime/Serial Experiments Lain/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
                  relative_path: "Serial Experiments Lain/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
                  route: "remux",
                  completed_at: "Jun 2 10:14 PM",
                },
                {
                  media_type: "Movie",
                  lookup_title: "Movie (2024)",
                  output_file: "Movie (2024).mkv",
                  output_path: "D:/Outsource/Movies/Movie (2024)/Movie (2024).mkv",
                  route_label: "ENCODE",
                  completed_at: "Jun 2 10:13 PM",
                },
              ],
            });
            const tbody = elements["home-recent-completed-tbody"];
            const tvRow = tbody.children[0];
            const fileCell = tvRow.cells[0];
            const title = fileCell.children[0]?.textContent || "";
            const meta = fileCell.children[1]?.textContent || "";
            if (title !== "Serial Experiments Lain - S02E01 - Weird.mkv") {
              throw new Error(`Expected concrete episode filename, got ${title}`);
            }
            if (!meta.includes("Serial Experiments Lain") || !meta.includes("Season 02")) {
              throw new Error(`Expected show/season context, got ${meta}`);
            }
            if (title.includes("TV (Season 02)")) {
              throw new Error(`Season-only lookup leaked into primary title: ${title}`);
            }
            if (tvRow.cells[1].textContent !== "REMUX") {
              throw new Error(`Route fallback did not render REMUX: ${tvRow.cells[1].textContent}`);
            }
            const movieRow = tbody.children[1];
            if ((movieRow.cells[0].children[0]?.textContent || "") !== "Movie (2024)") {
              throw new Error(`Movie lookup title changed unexpectedly: ${movieRow.cells[0].textContent}`);
            }
            if (movieRow.cells[1].textContent !== "ENCODE") {
              throw new Error(`Route label did not render ENCODE: ${movieRow.cells[1].textContent}`);
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_progress_csv_rerun_evidence_does_not_override_active_pipeline(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the progress CSV rerun classifier smoke.")
        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const progressPath = path.join(
              process.cwd(),
              "apps/desktop/webview/static/assets/progressView.js"
            );
            const source = fs.readFileSync(progressPath, "utf8");
            const progressChildren = ["barState.js", "barPresentation.js", "audit.js", "details.js", "worker.js", "csvRerun.js", "ffmpegEta.js", "activeWork.js", "diagnostics.js", "evidence.js", "evidenceRows.js", "timelineCore.js", "liveRun.js", "timelineView.js"].map((name) => {
              const childPath = path.join(process.cwd(), "apps/desktop/webview/static/assets/progress", name);
              return { childPath, source: fs.readFileSync(childPath, "utf8") };
            });
            const context = {
              window: {},
              console,
              Date,
              clearRows() {},
              appendCells() {},
              makeRowSelectable() {},
              setText() {},
              updateTableStatusLegend() {},
              byId() { return null; },
              mediaPipelineFormatters: { formatProgressValue(value) { return value == null ? "" : String(value); } },
            };
            context.window = context;
            vm.createContext(context);
            progressChildren.forEach(({ childPath, source }) => vm.runInContext(source, context, { filename: childPath }));
            vm.runInContext(source, context, { filename: progressPath });
            const progress = context.window.mediaPipelineProgressView;
            if (!progress?.csvRerunTailEvidence || !progress?.csvRerunActivityEvidence || !progress?.csvRerunTerminalLine || !progress?.liveRunStatus || !progress?.liveRunStripItems || !progress?.runTimelineItems) {
              throw new Error("Progress CSV rerun exports are missing");
            }

            const normalTail = progress.csvRerunTailEvidence({
              text: [
                "2026-07-01 11:43:43 [DEBUG] Copy attempt 1/3: Django Unchained.mkv",
                "2026-07-01 11:44:00 [INFO] Copying to scratch 38.9%",
                "2026-07-01 11:44:01 [INFO] Route: REMUX codec check pending",
              ].join("\n"),
            });
            if (normalTail.hasEvidence || normalTail.latestLine) {
              throw new Error(`Normal pipeline tail was classified as CSV rerun: ${JSON.stringify(normalTail)}`);
            }

            const staleCsvTail = {
              text: [
                "2026-07-01 11:40:00 [INFO] Rerun CSV rows listed: 100; enabled/planned: 100",
                "2026-07-01 11:40:01 [INFO] STAGE COPY attempt 1/3: Old Csv Item.mkv -> scratch",
              ].join("\n"),
            };
            const explicitTail = progress.csvRerunTailEvidence(staleCsvTail);
            if (!explicitTail.hasEvidence || !explicitTail.currentImport.includes("Old Csv Item")) {
              throw new Error(`Explicit CSV tail was not detected: ${JSON.stringify(explicitTail)}`);
            }

            const activePipelineContext = {
              stdoutTail: staleCsvTail,
              closeReadiness: { safe_to_close: false },
              snapshot: {
                pipeline_state: "processing",
                worker_progress: {
                  rows: [{
                    worker_label: "Local pipeline",
                    job_kind: "pipeline",
                    stage: "copy_to_scratch",
                    status: "active",
                    status_state: "running",
                    source: "Django Unchained (2012).mp4",
                    last_log_line: "2026-07-01 11:44:00 [INFO] Copying to scratch 38.9%",
                  }],
                },
              },
            };
            const suppressed = progress.csvRerunActivityEvidence(activePipelineContext);
            if (suppressed.hasEvidence || !suppressed.tailSuppressedByPipelineWorker) {
              throw new Error(`Stale CSV tail was not suppressed by active pipeline worker: ${JSON.stringify(suppressed)}`);
            }
            const liveStatus = progress.liveRunStatus(activePipelineContext);
            if (liveStatus.label !== "Active work") {
              throw new Error(`Active normal pipeline was labelled incorrectly: ${JSON.stringify(liveStatus)}`);
            }

            const activeRerun = progress.csvRerunActivityEvidence({
              stdoutTail: staleCsvTail,
              closeReadiness: { safe_to_close: false },
              snapshot: {
                worker_progress: {
                  rows: [{
                    worker_label: "Local rerun_csv",
                    job_kind: "rerun_csv",
                    stage: "active",
                    status: "active",
                    status_state: "running",
                    last_log_line: "2026-07-01 11:40:01 [INFO] STAGE COPY attempt 1/3: Old Csv Item.mkv -> scratch",
                  }],
                },
              },
            });
            if (!activeRerun.hasEvidence || !activeRerun.workerActive || !activeRerun.currentImport.includes("Old Csv Item")) {
              throw new Error(`Active CSV rerun worker was not preserved: ${JSON.stringify(activeRerun)}`);
            }

            const subtitleOcrWork = {
              stdoutTail: {
                text: "2026-07-01 11:40:00 [INFO] Rerun CSV rows listed: 100; enabled/planned: 100",
              },
              closeReadiness: { safe_to_close: false },
              snapshot: {
                pipeline_state: "processing",
                current_work: {
                  item_label: "Paprika (2006)",
                  phase_label: "CSV rerun",
                  current_stage_label: "Subtitle OCR: VobSub stream 3, 752 cues",
                  latest_evidence_label: "Subtitle OCR: VobSub stream 3, 752 cues",
                  summary_label: "Subtitle OCR: VobSub stream 3, 752 cues",
                  next_stage_label: "encode/remux output evidence",
                  route_label: "Encode route",
                  queue_position_label: "item 4 of 100",
                  evidence_status: "active",
                },
                progress: {
                  Status: "Processing",
                  CurrentStage: "csv_rerun",
                  CurrentFileDisplay: "Paprika.2006.1080p.BluRay.x264.mkv",
                  CurrentQueueIndex: 4,
                  CurrentQueueTotal: 100,
                  CurrentRoute: "encode",
                },
                progress_bars: [
                  { id: "subtitle_track", label: "Subtitle VOBSUB stream 3", status: "active", detail: "2 / 4 | ocr | 752 cue(s)" },
                ],
                worker_progress: {
                  rows: [{
                    worker_label: "Local rerun_csv",
                    job_kind: "rerun_csv",
                    status_state: "running",
                    last_log_line: "Rerun CSV rows listed: 100; enabled/planned: 100",
                  }],
                },
              },
            };
            const liveItems = progress.liveRunStripItems(subtitleOcrWork);
            if (liveItems[0]?.label !== "Now" || !liveItems[0]?.value.includes("Subtitle OCR: VobSub stream 3, 752 cues")) {
              throw new Error(`Live Run did not prefer backend active-work summary: ${JSON.stringify(liveItems.slice(0, 4))}`);
            }
            if (liveItems.some((item) => item.label === "Importing" && item.value === "No current import line")) {
              throw new Error(`Live Run rendered misleading import fallback despite backend OCR evidence: ${JSON.stringify(liveItems)}`);
            }
            const ocrTimeline = progress.runTimelineItems(subtitleOcrWork);
            const subtitleStep = ocrTimeline.find((item) => item.id === "subtitle_work");
            if (!subtitleStep?.current || !subtitleStep.detail.includes("Subtitle OCR: VobSub stream 3, 752 cues")) {
              throw new Error(`Run Progress did not mark subtitle OCR as current work: ${JSON.stringify(ocrTimeline)}`);
            }

            const csvTimeline = progress.runTimelineItems({
              stdoutTail: staleCsvTail,
              closeReadiness: { safe_to_close: false },
              snapshot: {
                pipeline_state: "processing",
                progress: {
                  Status: "Processing",
                  CurrentStage: "Encoding",
                  CurrentStagePercent: 12,
                  CurrentFileDisplay: "Old Csv Item.mkv",
                  CurrentQueueIndex: 4,
                  CurrentQueueTotal: 100,
                  CurrentRoute: "encode",
                },
                progress_bars: [
                  { id: "current_stage", label: "Current backend stage", status: "active", percent: 12, detail: "Encoding | Old Csv Item.mkv" },
                ],
                worker_progress: { rows: [] },
              },
            });
            const timelineLabels = csvTimeline.map((item) => item.label);
            for (const label of ["CSV import", "Queue item", "Copy to scratch", "Route selected: encode", "Encode output", "Publish or park", "Run evidence"]) {
              if (!timelineLabels.includes(label)) {
                throw new Error(`CSV timeline label missing ${label}: ${timelineLabels.join(" | ")}`);
              }
            }
            if (csvTimeline[0].label !== "CSV import" || !csvTimeline[0].current || !csvTimeline.some((item) => item.next)) {
              throw new Error(`CSV timeline did not mark current/next steps: ${JSON.stringify(csvTimeline)}`);
            }
            const csvLoadedTimeline = progress.runTimelineItems({
              stdoutTail: {
                text: [
                  "2026-07-05 01:24:17 [INFO] Rerun CSV rows listed: 1; enabled/planned: 1",
                  "2026-07-05 01:24:18 [INFO] STAGED copy: Breakfast at Tiffany's (1961).mkv",
                  "2026-07-05 01:24:19 [DEBUG] ENCODE : still running...",
                ].join("\n"),
              },
              snapshot: {
                pipeline_state: "processing",
                current_work: {
                  latest_evidence_label: "2026-07-05 01:24:19 [DEBUG] ENCODE : still running...",
                },
                worker_progress: {
                  rows: [{
                    worker_label: "Local rerun_csv",
                    job_kind: "rerun_csv",
                    status_state: "running",
                    last_log_line: "2026-07-05 01:24:19 [DEBUG] ENCODE : still running...",
                  }],
                },
              },
            });
            const csvLoadedImport = csvLoadedTimeline[0];
            if (!csvLoadedImport.detail.includes("Loaded Breakfast at Tiffany's (1961).mkv") || !csvLoadedImport.detail.includes("Waiting for encode to finish")) {
              throw new Error(`CSV loaded import detail was not compact/useful: ${JSON.stringify(csvLoadedImport)}`);
            }
            for (const verboseText of ["CSV rerun evidence loaded", "[DEBUG]", "Backend evidence"]) {
              if (csvLoadedImport.detail.includes(verboseText)) {
                throw new Error(`CSV loaded import detail still includes verbose text ${verboseText}: ${csvLoadedImport.detail}`);
              }
            }
            if (csvLoadedImport.evidence !== "Last event: 01:24:19 Encode still running") {
              throw new Error(`CSV loaded import evidence was not normalized: ${JSON.stringify(csvLoadedImport)}`);
            }
            const csvWaitingContext = {
              stdoutTail: {
                text: [
                  "2026-07-03 20:05:37 [INFO] Rerun CSV rows listed: 2; enabled/planned: 2",
                  "2026-07-03 20:05:38 [INFO] STAGED copy: Up (2009).mkv",
                  "2026-07-03 20:05:39 [INFO] Nested pipeline chunk 4 exited with code 0",
                ].join("\n"),
              },
              closeReadiness: { safe_to_close: false, state: "running", reason: "CSV rerun active work is still running." },
              snapshot: {
                pipeline_state: "idle",
                current_work: {
                  phase_label: "Idle",
                  current_stage_label: "Idle",
                  latest_event_label: "tool_completed · subtitle-helper",
                  evidence_status: "idle",
                },
                progress: {
                  Status: "idle / waiting for next item",
                  CurrentStage: "idle",
                  CurrentFileDisplay: "None",
                  TotalProcessed: 1,
                  Encoded: 1,
                  Remuxed: 0,
                  Failed: 0,
                },
                progress_bars: [],
                worker_progress: { rows: [] },
                recent_events: [{
                  event_type: "tool_completed",
                  stage: "subtitle-helper",
                  status: "stopped",
                  data: { completion_status: "stopped" },
                }],
              },
            };
            const csvWaitingTimeline = progress.runTimelineItems(csvWaitingContext);
            const csvWaitingCurrent = csvWaitingTimeline.find((item) => item.current);
            if (csvWaitingCurrent?.id !== "csv_import" || csvWaitingCurrent.status !== "active") {
              throw new Error(`CSV waiting timeline focused the wrong step: ${JSON.stringify(csvWaitingTimeline)}`);
            }
            const csvWaitingRunEvidence = csvWaitingTimeline.find((item) => item.id === "run_evidence");
            if (csvWaitingRunEvidence?.current || !csvWaitingTimeline[0]?.detail.includes("Waiting for nested pipeline")) {
              throw new Error(`CSV waiting timeline still made run evidence look current: ${JSON.stringify(csvWaitingTimeline)}`);
            }
            const csvWaitingStatus = progress.liveRunStatus(csvWaitingContext);
            if (csvWaitingStatus.label !== "CSV rerun active") {
              throw new Error(`CSV waiting status was not specific: ${JSON.stringify(csvWaitingStatus)}`);
            }
            const pendingRouteTimeline = progress.runTimelineItems({
              snapshot: {
                pipeline_state: "processing",
                progress: {
                  Status: "Processing",
                  CurrentStage: "csv_rerun",
                  CurrentFileDisplay: "Route Pending Fixture.mkv",
                  CurrentQueueIndex: 1,
                  CurrentQueueTotal: 2,
                },
                progress_bars: [],
                worker_progress: { rows: [] },
              },
            });
            const pendingRouteStep = pendingRouteTimeline.find((item) => item.id === "route_selected");
            if (pendingRouteStep?.label !== "Route decision pending" || !pendingRouteStep?.detail.includes("No backend route is selected yet")) {
              throw new Error(`Route-pending timeline still claimed selection: ${JSON.stringify(pendingRouteStep)}`);
            }

            const terminalLines = [
              "PLAN ONLY complete. No manifest, temp config, stage, park, output, or source paths were written.",
              "DRY RUN complete. Manifest: C:\\Local\\RerunManifests\\rerun.json",
              "Rerun batch complete. Manifest: C:\\Local\\RerunManifests\\rerun.json",
              "CSV rerun failed: source file not found",
              "Nested pipeline exited with code 1",
            ];
            for (const line of terminalLines) {
              if (!progress.csvRerunTerminalLine(line)) {
                throw new Error(`Terminal CSV rerun line was not detected: ${line}`);
              }
              const terminal = progress.csvRerunActivityEvidence({
                stdoutTail: {
                  text: [
                    "2026-07-01 11:40:00 [INFO] Rerun CSV rows listed: 100; enabled/planned: 100",
                    line,
                  ].join("\n"),
                },
                closeReadiness: { safe_to_close: false },
                snapshot: { worker_progress: { rows: [] } },
              });
              if (!terminal.hasEvidence || terminal.isActive) {
                throw new Error(`Terminal CSV rerun tail kept activity active: ${JSON.stringify(terminal)}`);
              }
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_home_live_work_summary_renders_before_launch_preflight_await(self) -> None:
        repo_root = find_repo_root(Path(__file__))
        assets_root = repo_root / "apps" / "desktop" / "webview" / "static" / "assets"
        app_js = "\n".join(
            (assets_root / path).read_text(encoding="utf-8")
            for path in ("app/refreshCoordinator.js", "app.js")
        )

        self.assertIn("function renderLiveWorkHomeSummary", app_js)
        self.assertGreaterEqual(app_js.count("renderLiveWorkHomeSummary(liveRunContext)"), 2)
        refresh_tail_block = app_js[
            app_js.index("async function refreshLiveRunTail") :
            app_js.index("async function refreshAll")
        ]
        full_refresh_preflight_block = app_js[
            app_js.index("async function refreshAllNow") :
            app_js.index("const launchPanel = document.querySelector")
        ]
        self.assertIn("renderLiveWorkHomeSummary(liveRunContext)", refresh_tail_block)
        self.assertIn("renderLiveWorkHomeSummary(liveRunContext)", full_refresh_preflight_block)
        self.assertLess(
            app_js.rindex("renderLiveWorkHomeSummary(liveRunContext)"),
            app_js.index("await launchView.refreshLaunchBackendPreflight();"),
        )

    def test_refresh_requests_only_core_and_active_page_routes(self) -> None:
        repo_root = find_repo_root(Path(__file__))
        assets_root = repo_root / "apps" / "desktop" / "webview" / "static" / "assets"
        app_js = "\n".join(
            (assets_root / path).read_text(encoding="utf-8")
            for path in ("app/refreshCoordinator.js", "app/lifecycleOrchestration.js")
        )

        self.assertIn("function activeRefreshPage", app_js)
        self.assertIn("function refreshRequestIncluded", app_js)
        self.assertIn('settings: new Set(["settings", "preset library"])', app_js)
        self.assertIn(".filter(([name]) => refreshRequestIncluded(name, refreshPage, refreshOptions))", app_js)
        self.assertIn("if (options.initialCritical) return CORE_REFRESH_REQUESTS.has(name);", app_js)
        self.assertIn('refreshAll({ automatic: true, initialCritical: true, page: "home" })', app_js)
        self.assertIn('schema_version: "webview_startup_performance.v1"', app_js)
        self.assertNotIn('["contract", "/api/contract", false]', app_js)

    def test_home_next_queue_shows_first_five_runnable_rows_only(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the Home next-queue formatter smoke.")
        repo_root = find_repo_root(Path(__file__))
        static_root = repo_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        next_queue_start = html.index("home-next-queue-status")
        next_queue_end = html.index("<!-- ═══ DAILY DRIVER: RUN PROGRESS ═══ -->")
        next_queue_section = html[next_queue_start:next_queue_end]
        self.assertNotIn("Review Queue", next_queue_section)
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const homePath = path.join(
              process.cwd(),
              "apps/desktop/webview/static/assets/app/home.js"
            );
            const source = [
              "apps/desktop/webview/static/assets/app/home/dailyDriver.js",
              "apps/desktop/webview/static/assets/app/home/queueProjection.js",
              "apps/desktop/webview/static/assets/app/home.js",
            ].map((name) => fs.readFileSync(path.join(process.cwd(), name), "utf8")).join("\n");
            function makeElement(tag) {
              const node = {
                tagName: String(tag || "").toUpperCase(),
                children: [],
                title: "",
                dataset: {},
                className: "",
                classList: {
                  add(value) { node.className = [node.className, value].filter(Boolean).join(" "); },
                  toggle(value, force) {
                    const classes = new Set(String(node.className || "").split(/\s+/).filter(Boolean));
                    const enabled = force === undefined ? !classes.has(value) : Boolean(force);
                    if (enabled) classes.add(value);
                    else classes.delete(value);
                    node.className = Array.from(classes).join(" ");
                  },
                },
                setAttribute(name, value) { this[name] = String(value); },
                addEventListener() {},
                appendChild(child) { this.children.push(child); return child; },
                append(...items) { items.forEach((item) => this.appendChild(item)); },
                replaceChildren(...items) { this.children = []; this.append(...items); },
                _textContent: "",
              };
              Object.defineProperty(node, "textContent", {
                get() { return this._textContent || this.children.map((child) => child.textContent || "").join(""); },
                set(value) { this._textContent = String(value ?? ""); this.children = []; },
              });
              return node;
            }
            const elements = {
              "home-next-queue-list": makeElement("ol"),
              "home-next-queue-detail": makeElement("p"),
              "home-next-queue-status": makeElement("strong"),
            };
            const context = {
              window: {},
              console,
              document: { createElement: makeElement },
              byId(id) { return elements[id] || null; },
              appendCells() {},
              clearRows() {},
              makeRowSelectable() {},
              setText(id, value) { if (elements[id]) elements[id].textContent = value; },
              mediaPipelineFormatters: { formatProgressValue(value) { return value == null ? "" : String(value); } },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: homePath });
            const home = context.window.mediaPipelineAppHome;
            if (!home?.renderHomeNextQueue) throw new Error("Home next-queue renderer export is missing");
            home.renderHomeNextQueue({
              queue: {
                rows: [
                  {
                    media_kind: "tv",
                    relative_path: "Serial Experiments Lain\\Season 02\\Serial Experiments Lain S02E01 Weird.mkv",
                    display_name: "Serial Experiments Lain S02E01 Weird.mkv",
                    route_name: "REMUX (codec check pending)",
                    operator_status: "Ready",
                    queue_position: "1/9",
                  },
                  { display_name: "Completed Should Hide.mkv", route_name: "REMUX", operator_status: "Recently completed", queue_position: "2/9" },
                  { display_name: "Blocked Should Hide.mkv", route_name: "REMUX", operator_status: "Blocked", blocked_reason: "already processed", queue_position: "3/9" },
                  { display_name: "Invalid Should Hide.mkv", route_name: "REMUX", operator_status: "Invalid snapshot row", queue_position: "4/9" },
                  { media_kind: "movie", display_name: "Cast.Away.2000.1080p.BluRay.x264.mkv", route_name: "ENCODE", operator_status: "Priority ready", queue_position: "5/9" },
                  { display_name: "Ready Three.mkv", route_name: "REMUX", operator_status: "Ready", queue_position: "6/9" },
                  { display_name: "Ready Four.mkv", route_name: "REMUX", operator_status: "Ready", queue_position: "7/9" },
                  { display_name: "Ready Five.mkv", route_name: "REMUX", operator_status: "Ready", queue_position: "8/9" },
                  { display_name: "Ready Six Should Cap.mkv", route_name: "REMUX", operator_status: "Ready", queue_position: "9/9" },
                ],
              },
            });
            const list = elements["home-next-queue-list"];
            const rendered = list.children.map((item) => item.textContent);
            if (rendered.length !== 5) throw new Error(`Expected five rows, got ${rendered.length}: ${rendered.join(" | ")}`);
            for (const expected of ["Serial Experiments Lain", "S02E01", "REMUX", "Cast Away (2000)", "Ready Three.mkv", "Ready Four.mkv", "Ready Five.mkv"]) {
              if (!rendered.some((line) => line.includes(expected))) throw new Error(`Missing ${expected}: ${rendered.join(" | ")}`);
            }
            for (const forbidden of ["codec check pending", "Weird", "Completed Should Hide", "Blocked Should Hide", "Invalid Should Hide", "Ready Six Should Cap"]) {
              if (rendered.some((line) => line.includes(forbidden))) throw new Error(`Unexpected ${forbidden}: ${rendered.join(" | ")}`);
            }
            if (elements["home-next-queue-status"].textContent !== "5 ready") {
              throw new Error(`Unexpected status: ${elements["home-next-queue-status"].textContent}`);
            }
            const detail = elements["home-next-queue-detail"].textContent;
            for (const expected of ["Route:", "REMUX", "Status:", "Ready", "Queue:", "1/9", "Source:", "Season 02", "Output:", "Not loaded", "Open Queue for full row evidence"]) {
              if (!detail.includes(expected)) throw new Error(`Missing detail ${expected}: ${detail}`);
            }
            if (detail.includes("Selected queue item:") || detail.includes("Safe next step:")) {
              throw new Error(`Old verbose detail text is still rendered: ${detail}`);
            }
            home.renderHomeNextQueue({
              snapshot: {
                current_work: {
                  item_label: "Paprika (2006)",
                  current_stage_label: "Subtitle OCR: VobSub stream 3, 752 cues",
                  latest_evidence_label: "Subtitle OCR: VobSub stream 3, 752 cues",
                  next_stage_label: "encode/remux output evidence",
                  route_label: "Encode route",
                  queue_position_label: "item 4 of 100",
                  evidence_status: "active",
                },
                progress: {
                  CurrentFilePath: "C:\\Media\\Movies\\Paprika.2006.1080p.BluRay.x264.mkv",
                  CurrentFileDisplay: "Paprika.2006.1080p.BluRay.x264.mkv",
                  CurrentQueueIndex: 4,
                  CurrentQueueTotal: 100,
                  CurrentRoute: "encode",
                },
                counts: { queue_index: 4, processed: 3 },
              },
              queue: {
                rows: [
                  { media_kind: "movie", source_path: "C:\\Media\\Movies\\Previous.mkv", display_name: "Previous.mkv", route_name: "REMUX", operator_status: "Ready", queue_position: "3/100", global_order: 3 },
                  { media_kind: "movie", source_path: "C:\\Media\\Movies\\Paprika.2006.1080p.BluRay.x264.mkv", display_name: "Paprika.2006.1080p.BluRay.x264.mkv", route_name: "ENCODE", operator_status: "Ready", queue_position: "4/100", global_order: 4 },
                  { media_kind: "movie", source_path: "C:\\Media\\Movies\\Delicatessen.1991.mkv", display_name: "Delicatessen.1991.mkv", route_name: "REMUX", operator_status: "Ready", queue_position: "5/100", global_order: 5 },
                ],
              },
            });
            const activeRendered = list.children.map((item) => item.textContent);
            if (list.children[0]?.dataset.current !== "true") {
              throw new Error(`Current row was not marked in Next 5 Videos: ${JSON.stringify(list.children[0]?.dataset || {})}`);
            }
            if (!activeRendered[0]?.includes("Paprika") || !activeRendered[0]?.includes("Current") || !activeRendered[0]?.includes("Subtitle OCR: VobSub stream 3, 752 cues")) {
              throw new Error(`Current active-work row was not rendered first: ${activeRendered.join(" | ")}`);
            }
            const activeDetail = elements["home-next-queue-detail"].textContent;
            for (const expected of ["Current stage:", "Subtitle OCR: VobSub stream 3, 752 cues", "Evidence:", "Next:", "encode/remux output evidence"]) {
              if (!activeDetail.includes(expected)) throw new Error(`Missing active row detail ${expected}: ${activeDetail}`);
            }
            context.mediaPipelineProgressView = {
              csvRerunTailEvidence() {
                return {
                  hasEvidence: true,
                  plannedRows: "100 enabled / 100 CSV rows",
                  currentImport: "Clueless (1995).mp4",
                  lastImported: "Caddyshack (1980).mkv",
                  processing: "Not processing yet; importing staged CSV files",
                  latestLine: "STAGE COPY attempt 1/3: Clueless (1995).mp4 -> scratch",
                };
              },
            };
            home.renderHomeNextQueue({
              stdoutTail: { text: "csv active" },
              closeReadiness: { safe_to_close: false },
              queue: { rows: [] },
            });
            const csvRendered = list.children.map((item) => item.textContent);
            if (elements["home-next-queue-status"].textContent !== "CSV rerun active") {
              throw new Error(`CSV rerun status did not replace queue status: ${elements["home-next-queue-status"].textContent}`);
            }
            for (const expected of ["Importing: Clueless (1995).mp4", "Last imported: Caddyshack (1980).mkv", "Processing: Not processing yet", "CSV rows: 100 enabled / 100 CSV rows"]) {
              if (!csvRendered.some((line) => line.includes(expected))) throw new Error(`Missing CSV row ${expected}: ${csvRendered.join(" | ")}`);
            }
            const csvDetail = elements["home-next-queue-detail"].textContent;
            for (const expected of ["Importing:", "Clueless (1995).mp4", "CSV rows:", "100 enabled / 100 CSV rows", "still importing staged files"]) {
              if (!csvDetail.includes(expected)) throw new Error(`Missing CSV detail ${expected}: ${csvDetail}`);
            }
            context.mediaPipelineProgressView = {
              csvRerunActivityEvidence(activityContext) {
                const rows = activityContext?.snapshot?.worker_progress?.rows || [];
                if (!rows.some((row) => String(row.worker_label || "").includes("rerun csv"))) {
                  throw new Error("CSV activity renderer did not receive worker-progress context");
                }
                return {
                  hasEvidence: true,
                  isActive: true,
                  workerActive: true,
                  plannedRows: "100 enabled / 100 CSV rows",
                  currentImport: "Jurassic World Fallen Kingdom (2018).mkv",
                  lastImported: "Fumetsu No Anata E S02E05.mkv",
                  processing: "Not processing yet; importing staged CSV files",
                  latestLine: "PIPELINE SHUTDOWN CLEANLY",
                };
              },
            };
            home.renderHomeNextQueue({
              stdoutTail: { text: "PIPELINE SHUTDOWN CLEANLY" },
              closeReadiness: { safe_to_close: false },
              snapshot: {
                worker_progress: {
                  rows: [
                    {
                      worker_label: "Local rerun csv",
                      stage: "active",
                      status_state: "running",
                      last_log_line: "STAGE COPY attempt 1/3: Jurassic World Fallen Kingdom (2018).mkv -> scratch",
                    },
                  ],
                },
              },
              queue: { rows: [] },
            });
            const workerCsvRendered = list.children.map((item) => item.textContent);
            if (elements["home-next-queue-status"].textContent !== "CSV rerun active") {
              throw new Error(`CSV worker status did not replace queue status: ${elements["home-next-queue-status"].textContent}`);
            }
            if (!workerCsvRendered.some((line) => line.includes("Importing: Jurassic World Fallen Kingdom (2018).mkv"))) {
              throw new Error(`CSV worker row was not rendered: ${workerCsvRendered.join(" | ")}`);
            }
            context.mediaPipelineProgressView = {
              csvRerunActivityEvidence(activityContext) {
                const rows = activityContext?.snapshot?.worker_progress?.rows || [];
                if (!rows.some((row) => String(row.worker_label || "").includes("rerun csv"))) {
                  throw new Error("CSV queue renderer did not receive worker-progress context");
                }
                return {
                  hasEvidence: true,
                  hasWorkerEvidence: true,
                  isActive: false,
                  workerActive: false,
                  processing: "[INFO] ENCODE : 55%",
                  latestLine: "[INFO] ENCODE : 55%",
                };
              },
            };
            home.renderHomeNextQueue({
              snapshot: {
                worker_progress: {
                  rows: [
                    {
                      worker_label: "Local rerun csv",
                      status_state: "running",
                      last_log_line: "[INFO] ENCODE : 55%",
                    },
                  ],
                },
              },
              queue: {
                rows: [
                  {
                    media_kind: "movie",
                    display_name: "Paprika(2006).mkv",
                    route_name: "ENCODE",
                    operator_status: "Ready",
                    queue_position: "4/100",
                    queue_source: "csv_rerun",
                    queue_phase: "csv_rerun",
                  },
                  {
                    media_kind: "movie",
                    display_name: "Delicatessen (1991).mkv",
                    route_name: "REMUX",
                    operator_status: "Ready",
                    queue_position: "5/100",
                  },
                ],
              },
            });
            const csvQueueRendered = list.children.map((item) => item.textContent);
            if (elements["home-next-queue-status"].textContent !== "CSV rerun queue · 2 queued") {
              throw new Error(`CSV rerun queue status was not shown: ${elements["home-next-queue-status"].textContent}`);
            }
            if (!csvQueueRendered.some((line) => line.includes("Paprika") && line.includes("CSV rerun") && line.includes("ENCODE"))) {
              throw new Error(`CSV rerun queue row was not labelled: ${csvQueueRendered.join(" | ")}`);
            }
            const csvQueueDetail = elements["home-next-queue-detail"].textContent;
            for (const expected of ["Workflow:", "CSV rerun queue", "Queue:", "4/100", "active CSV rerun queue"]) {
              if (!csvQueueDetail.includes(expected)) throw new Error(`Missing CSV queue detail ${expected}: ${csvQueueDetail}`);
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_web_and_tauri_shell_reference_all_local_api_contract_routes(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        asset_text = _render_static_index_html(static_root)
        for asset in (static_root / "assets").rglob("*.js"):
            asset_text += "\n" + asset.read_text(encoding="utf-8")
        tauri_lib = desktop_root / "apps" / "desktop" / "tauri" / "src-tauri" / "src" / "lib.rs"
        shell_text = tauri_lib.read_text(encoding="utf-8") if tauri_lib.exists() else ""
        tauri_contract_root = (
            desktop_root / "apps" / "desktop" / "tauri" / "src-tauri" / "src" / "backend_contract"
        )
        if tauri_contract_root.exists():
            for rust_source in tauri_contract_root.rglob("*.rs"):
                shell_text += "\n" + rust_source.read_text(encoding="utf-8")
        combined = asset_text + "\n" + shell_text

        backend_only_routes_without_current_web_controls = {
            "/api/diagnostics/tdarr-matrix/runs",
            "/api/queue/file-overrides/folder-preview",
            "/api/queue/file-overrides/folder-rule",
            "/api/settings/preset-library",
            "/api/settings/preset-library/validate",
            "/api/settings/preset-library/compare",
            "/api/settings/preset-library/import-preview",
            "/api/settings/preset-library/save",
            "/api/settings/preset-library/export",
            "/api/settings/preset-library/apply-preview",
            "/api/settings/preset-library/apply",
            "/api/settings/import-psd1-preview",
            "/api/settings/import-psd1",
            "/api/subtitle-qa/summary",
            "/api/subtitle-qa/item",
            "/api/subtitle-qa/preview",
            "/api/maintenance/retention-dry-run",
        }
        route_paths = [
            route["path"]
            for route in LOCAL_API_READ_ROUTE_CONTRACT + LOCAL_API_COMMAND_ROUTE_CONTRACT
            if route["path"] not in backend_only_routes_without_current_web_controls
        ]
        missing = [path for path in route_paths if path not in combined]

        self.assertEqual(missing, [])

    def test_web_controls_expose_local_api_command_allowlists(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        app_row_open_js = (static_root / "assets" / "app" / "rowOpenActions.js").read_text(encoding="utf-8")
        reports_shell_js = (static_root / "assets" / "reports" / "shell.js").read_text(encoding="utf-8")
        command_routes = {str(route["path"]): route for route in LOCAL_API_COMMAND_ROUTE_CONTRACT}

        def row_open_targets(scope: str) -> set[str]:
            key_pattern = (
                re.escape(f'"{scope}"')
                if "-" in scope
                else rf"(?<![A-Za-z0-9_$]){re.escape(scope)}"
            )
            pattern = rf"{key_pattern}:\s*\{{.*?actions:\s*\[(.*?)\],\s*onOpen"
            match = re.search(pattern, app_row_open_js, re.S)
            self.assertIsNotNone(match, f"row open action config missing for {scope}")
            return set(re.findall(r'target:\s*"([^"]+)"', match.group(1)))

        diagnostics_targets = set(re.findall(r'data-open-diagnostics="([^"]+)"', html))
        report_target_match = re.search(r"function reportOpenTarget\(key\).*?const targets = \{(.*?)\};", reports_shell_js, re.S)
        self.assertIsNotNone(report_target_match)
        diagnostics_targets.update(re.findall(r':\s*"([^"]+)"', report_target_match.group(1)))
        self.assertEqual(set(command_routes["/api/diagnostics/open"]["allowed_targets"]) - diagnostics_targets, set())

        queue_targets = row_open_targets("queue")
        self.assertEqual(set(command_routes["/api/queue/open"]["allowed_targets"]) - queue_targets, set())
        queue_excluded_targets = row_open_targets("queue-excluded")
        self.assertEqual(set(command_routes["/api/queue/open"]["allowed_targets"]) - queue_excluded_targets, set())
        self.assertEqual(set(command_routes["/api/queue/open"]["allowed_row_scopes"]), {"runnable", "excluded"})

        completed_targets = row_open_targets("completed")
        self.assertIn("Play Output", app_row_open_js)
        self.assertNotIn("Open Output File", app_row_open_js)
        self.assertIn("play_output_file", completed_targets)
        self.assertNotIn("output_file", completed_targets)
        completed_route_targets = set(command_routes["/api/completed/open"]["allowed_targets"])
        self.assertEqual((completed_route_targets - {"output_file"}) - completed_targets, set())

        pending_targets = row_open_targets("pending")
        self.assertIn("play_local_file", pending_targets)
        self.assertNotIn("local_file", pending_targets)
        pending_route_targets = set(command_routes["/api/pending-publish/open"]["allowed_targets"])
        self.assertEqual((pending_route_targets - {"local_file"}) - pending_targets, set())
        self.assertEqual(set(command_routes["/api/pending-publish/recovery-plan"]["allowed_scopes"]), {"all", "selected"})

        control_actions = set(re.findall(r'data-control-action="([^"]+)"', html))
        self.assertEqual(set(command_routes["/api/pipeline/control"]["allowed_actions"]) - control_actions, set())

        self.assertIn('id="pipeline-single-file-browse-button"', html)
        self.assertIn('id="pipeline-single-file-clear-button"', html)
        self.assertEqual(command_routes["/api/pipeline/browse-file"]["allowed_selection_modes"], ["files"])
        mode_match = re.search(r'<select id="pipeline-start-mode"[^>]*>(.*?)</select>', html, re.S)
        self.assertIsNotNone(mode_match)
        mode_options = set(re.findall(r'<option value="([^"]*)"', mode_match.group(1)))
        self.assertEqual(set(command_routes["/api/pipeline/start"]["allowed_modes"]) - mode_options, set())
        self.assertIn('<option value="once" selected>Run Once</option>', mode_match.group(1))

        schedule_match = re.search(r'<select id="pipeline-start-schedule-override">(.*?)</select>', html, re.S)
        self.assertIsNotNone(schedule_match)
        schedule_options = set(re.findall(r'<option value="([^"]*)"', schedule_match.group(1)))
        self.assertEqual(set(command_routes["/api/pipeline/start"]["allowed_schedule_overrides"]) - schedule_options, set())

    def test_home_pipeline_state_metric_uses_naturalized_text_renderer(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        app_js = "\n".join(
            (static_root / "assets" / path).read_text(encoding="utf-8")
            for path in ("app/dashboard.js", "app/refreshCoordinator.js", "app.js")
        )
        topbar_js = (static_root / "assets" / "app" / "topbar.js").read_text(encoding="utf-8")
        components_css = _read_components_css(static_root / "assets")

        self.assertIn('id="pipeline-state" class="pipeline-state-value"', html)
        self.assertIn('class="pipeline-state-main"', html)
        self.assertIn('class="pipeline-state-detail" hidden', html)
        self.assertIn('id="queue-count-detail" class="metric-detail"', html)
        self.assertIn('class="panel live-run-strip-panel" data-panel-type="status"', html)
        self.assertIn("const HOME_PIPELINE_STATE_LABELS = Object.freeze({", topbar_js)
        self.assertIn('csv_rerun_active: { main: "CSV Rerun", detail: "active" }', topbar_js)
        self.assertIn('remuxing_movie: { main: "Remuxing Movie", detail: "" }', topbar_js)
        self.assertIn('"encoding_tv_(cpu_fallback)": { main: "Encoding TV", detail: "(cpu fallback)" }', topbar_js)
        self.assertIn(
            '"waiting_for_cpu_slot_(audio_transcode)": { main: "Waiting For CPU Slot", detail: "(audio transcode)" }',
            topbar_js,
        )
        self.assertIn('retrying_pending_push: { main: "Retrying Pending Publish", detail: "" }', topbar_js)
        self.assertIn('no_new_sources: { main: "No New Sources", detail: "" }', topbar_js)
        self.assertIn('const readable = raw.replace(/[_-]+/g, " ")', topbar_js)
        self.assertIn("renderHomePipelineState(state);", app_js)
        self.assertIn("function renderHomePipelineQueueOutcome", app_js)
        self.assertIn("const latestQueue = values.queue || lastQueue || {};", app_js)
        self.assertIn("renderHomePipelineQueueOutcome(values.snapshot || lastSnapshot, latestQueue);", app_js)
        self.assertIn(".pipeline-state-value {", components_css)
        self.assertIn('.metric strong[data-mode="file"]', components_css)
        self.assertIn("overflow-wrap: anywhere;", components_css)

    def test_app_refresh_uses_schedule_namespace_export(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        app_js = (static_root / "assets" / "app" / "refreshCoordinator.js").read_text(encoding="utf-8")

        self.assertIn("window.mediaPipelineScheduleView?.renderSchedule?.(values.schedule);", app_js)
        self.assertNotIn("renderSchedule(values.schedule);", app_js)

    def test_completed_open_inventory_documents_contract_targets(self) -> None:
        repo_root = find_repo_root(Path(__file__))
        route = next(
            route
            for route in LOCAL_API_COMMAND_ROUTE_CONTRACT
            if route["path"] == "/api/completed/open"
        )
        target_tokens = [f"`{target}`" for target in route["allowed_targets"]]
        inventory_paths = [
            repo_root / "docs" / "inventories" / "API_ROUTE_INVENTORY.md",
            repo_root / "docs" / "inventories" / "LOCAL_API_ROUTE_OWNERSHIP_MAP.md",
            repo_root / "docs" / "inventories" / "COMMAND_OWNERSHIP_MATRIX.md",
        ]

        for inventory_path in inventory_paths:
            text = inventory_path.read_text(encoding="utf-8")
            row = next(
                (line for line in text.splitlines() if "`POST /api/completed/open`" in line),
                "",
            )
            self.assertTrue(row, f"{inventory_path} missing completed open route row")
            for target_token in target_tokens:
                self.assertIn(
                    target_token,
                    row,
                    f"{inventory_path} missing {target_token} in completed open route row",
                )

    def test_dashboard_quick_controls_stay_simple_and_backend_owned(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        app_js = "\n".join(
            (static_root / "assets" / name).read_text(encoding="utf-8")
            for name in ("app.js", "app/refreshCoordinator.js")
        )
        home_js = (static_root / "assets" / "app" / "home.js").read_text(encoding="utf-8")
        home_match = re.search(
            r'<section class="page is-visible" data-page-panel="home">(.*?)<section class="page" data-page-panel="live">',
            html,
            re.S,
        )
        self.assertIsNotNone(home_match)
        home_html = home_match.group(1)
        for forbidden in [
            "home-pipeline-start-button",
            "home-drain-button",
            "home-schedule-toggle-button",
            "Run Controls",
            "Quick Actions",
            "Hard Kill",
            "Publish Parked Outputs",
        ]:
            self.assertNotIn(forbidden, home_html)
        home_actions = set(re.findall(r'data-control-action="([^"]+)"', home_html))
        self.assertEqual(home_actions, set())
        self.assertNotIn('data-control-action="rescan"', home_html)
        self.assertNotIn("Pause / Resume", home_html)
        self.assertNotIn("Stop After Current", home_html)
        self.assertNotIn("Force Stop", home_html)
        self.assertIn("Review readiness and choose a queue before anything runs. Originals stay unchanged.", home_html)
        self.assertIn('data-cross-page-target="completed" data-home-promotion-entry', home_html)
        self.assertIn("Open Completed Output", home_html)
        self.assertIn('id="home-scratch-storage-status"', home_html)
        self.assertIn('id="home-scratch-storage-detail"', home_html)
        self.assertIn('id="home-output-storage-status"', home_html)
        self.assertIn('id="home-output-storage-detail"', home_html)
        self.assertIn('id="home-failure-artifact-storage-status"', home_html)
        self.assertIn('id="home-failure-artifact-storage-detail"', home_html)
        self.assertIn("function renderHomeStorageHealth", home_js)
        self.assertIn("function setHomeFailureArtifactMetric", home_js)
        self.assertIn("homeFailureArtifactSummary(context)", home_js)
        self.assertIn('["failure artifacts", "/api/failures/artifacts", false]', app_js)
        self.assertIn('failureArtifacts: values["failure artifacts"] || {}', app_js)
        self.assertIn("homeActiveOutputPath", home_js)
        self.assertIn("renderHomeStorageHealth(dashboardContext)", app_js)
        self.assertIn('id="pipeline-start-button"', html)
        self.assertIn('id="pending-drain-button"', html)
        self.assertIn('data-control-action="pause"', html)
        self.assertIn('data-control-action="stop"', html)
        self.assertIn('data-control-action="kill"', html)

    def test_launch_controls_are_state_aware_and_topbar_kill_is_emergency_only(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        launch_js = _read_launch_view_asset_bundle(static_root / "assets")
        launch_scope_js = "\n".join(
            (static_root / "assets" / name).read_text(encoding="utf-8")
            for name in ("launch/scope/compactGate.js", "launchView.scope.js")
        )
        app_js = "\n".join(
            (static_root / "assets" / name).read_text(encoding="utf-8")
            for name in ("app.js", "app/refreshCoordinator.js")
        )
        app_lifecycle_js = "\n".join(
            (static_root / "assets" / name).read_text(encoding="utf-8")
            for name in ("app/lifecycle/navigation.js", "app/lifecycle.js")
        )
        styles_css = _read_components_css(static_root / "assets")
        controls_css = (static_root / "assets" / "styles.controls.css").read_text(encoding="utf-8")

        self.assertIn('class="danger-button emergency-button topbar-emergency-control"', html)
        self.assertIn('hidden aria-label="Emergency force stop related pipeline, audit, and CSV rerun processes"', html)
        self.assertIn("function updateLaunchCommandButtonStates", launch_js)
        self.assertIn("launchPipelineIsActive", launch_js)
        self.assertIn("function launchButtonGate", launch_js)
        self.assertIn("launchBackendPreflightPayloadForTarget", launch_js)
        self.assertIn("launchStartDecisionGate", launch_js)
        self.assertIn("await launchView.refreshLaunchBackendPreflight();", app_js)
        self.assertIn('document.querySelector(".launch-preflight-startup-alert")', app_js)
        self.assertIn("!refreshOptions.automatic || launchVisible || launchAlertVisible", app_js)
        self.assertIn("launchView.updateLaunchCommandButtonStates?.(", app_js)
        self.assertIn('return ["pipeline", "history"];', launch_js)
        self.assertIn('data-launch-tab="pipeline">Pipeline Processor</button>', html)
        self.assertNotIn('data-launch-tab="rerun"', html)
        self.assertNotIn('data-launch-tab="audit">Audit</button>', html)
        self.assertNotIn('data-launch-tab-panel="audit"', html)
        self.assertIn('id="rerun-open-audit-tool-button"', html)
        self.assertIn('id="rerun-open-latest-manifest-button"', html)
        self.assertIn('id="rerun-open-run-logs-button"', html)
        self.assertIn('id="rerun-open-last-stdout-button"', html)
        self.assertIn('id="rerun-open-last-stderr-button"', html)
        self.assertIn('id="rerun-open-active-jobs-button"', html)
        self.assertIn('id="rerun-show-command-history-button"', html)
        self.assertIn('data-cross-page-target="reports" data-cross-page-reports-tab="audit"', html)
        self.assertIn("function activateCrossPageTarget", app_lifecycle_js)
        self.assertIn("activateReportsTab?.(button.dataset.crossPageReportsTab)", app_lifecycle_js)
        self.assertIn('id="pipeline-compact-gate-strip"', html)
        self.assertIn('id="pipeline-compact-gate-detail"', html)
        self.assertIn('id="pipeline-compact-gate-refresh-button"', html)
        for gate_id in [
            "pipeline-gate-backend",
            "pipeline-gate-queue",
            "pipeline-gate-settings",
            "pipeline-gate-schedule",
            "pipeline-gate-active",
            "pipeline-gate-last",
        ]:
            self.assertIn(f'id="{gate_id}"', html)
        self.assertIn('aria-describedby="pipeline-start-disabled-reason"', html)
        self.assertIn("function launchCompactGateRows", launch_scope_js)
        self.assertIn("function launchCompactGateOverallStatus", launch_scope_js)
        self.assertIn("function launchCompactGateOpenTarget", launch_scope_js)
        self.assertIn("function launchCompactGateSettingsRows", launch_scope_js)
        self.assertIn("function activateLaunchTab(tabId, options = {})", launch_js)
        self.assertIn("const persist = options?.persist !== false;", launch_js)
        self.assertIn("launchCompactGateOpenTarget(item)", launch_scope_js)
        self.assertIn("function launchCompactGateActivateTargetTab", launch_scope_js)
        self.assertIn("is-attention-reveal", launch_scope_js)
        self.assertIn(
            'showPage: typeof showPage === "function" ? showPage : window.showPage,\n'
            "      activateLaunchTab: (...args) => activateLaunchTab(...args),",
            launch_js,
        )
        self.assertIn("Opened Diagnostics > Readiness > Backend Preflight", launch_scope_js)
        self.assertIn("Opened Queue > Queue-to-Launch handoff", launch_scope_js)
        self.assertIn("Opened Diagnostics > Readiness > Settings Check", launch_scope_js)
        self.assertIn("Opened Diagnostics > Readiness > Schedule Alignment", launch_scope_js)
        self.assertIn(".is-attention-target", styles_css)
        self.assertIn(".is-attention-reveal", styles_css)
        self.assertIn(".is-attention-reveal", controls_css)
        self.assertIn("function renderLaunchCompactGate", launch_scope_js)
        self.assertIn("launchCompactGateRows,", launch_js)
        self.assertIn("launchCompactGateOverallStatus,", launch_js)
        self.assertIn("renderLaunchCompactGate,", launch_js)
        self.assertNotIn("window.launchCompactGateRows =", launch_js)
        self.assertNotIn("window.renderLaunchCompactGate =", launch_js)
        self.assertNotIn("window.launchCompactGateOverallStatus =", launch_js)
        self.assertIn("Submitting ${label} for ${scope}. Backend will re-check queue, settings, schedule, and locks before starting.", launch_js)
        self.assertIn("Resolve blocked Backend Preflight checks", launch_js)
        self.assertIn("Resolve blocked Launch Start Summary rows", launch_js)
        self.assertIn("Refresh Backend Preflight before using this control", launch_js)
        self.assertIn("const stuck = pipelineProgressIsStuck(snapshot);", launch_js)
        self.assertIn("const killable = active || stuck;", launch_js)
        self.assertIn("button.hidden = !killable", launch_js)
        self.assertIn("let pipelineFileBrowseInFlight = false", launch_js)
        self.assertIn("function browsePipelineSingleFile", launch_js)
        self.assertIn('apiPost("/api/pipeline/browse-file", request)', launch_js)
        self.assertIn("function clearPipelineSingleFile", launch_js)
        self.assertIn('setButtonClass(button, active ? "primary-button" : "secondary-button")', launch_js)
        self.assertIn("window.mediaPipelineLaunchView?.updateLaunchCommandButtonStates", app_js)

    def test_command_surfaces_do_not_treat_backend_rejections_as_success(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        assets_root = desktop_root / "apps" / "desktop" / "webview" / "static" / "assets"
        settings_js = _read_settings_asset_bundle(assets_root)
        launch_js = _read_launch_view_asset_bundle(assets_root)
        helpers_js = _read_dom_helpers_asset_bundle(assets_root)

        self.assertIn('setText("settings-patch-status", settingsResultStatusLabel(result, "Saved", "Save failed"))', settings_js)
        self.assertIn("lastSettingsPatchSaveEvidence = {", settings_js)
        self.assertIn("signature,", settings_js)
        self.assertIn("result,", settings_js)
        self.assertIn("if (result.ok) {", settings_js)
        self.assertIn("function scheduleSettingsPostSaveRefresh()", settings_js)
        save_block = settings_js[
            settings_js.index("async function saveSettingsPatch()") :
            settings_js.index("async function reloadSettingsFromDisk()")
        ]
        self.assertIn("clearSettingsPatchCandidate();\n      resetSettingsBuilderSyncState();", save_block)
        self.assertRegex(save_block, r"if \(result\.ok\) \{\s+scheduleSettingsPostSaveRefresh\(\);")
        self.assertLess(save_block.index("clearSettingsPatchCandidate();"), save_block.index("scheduleSettingsPostSaveRefresh();"))
        self.assertNotIn("await refreshAll();", save_block)
        self.assertNotIn('setText("settings-patch-status", "Saved")', settings_js)

        self.assertIn('if (result.ok) return result.severity === "warning" ? "Warning" : successLabel;', launch_js)
        self.assertIn('return result.severity || "Blocked";', launch_js)
        self.assertIn('`Result: ${payload.ok ? "ok" : "blocked"}', launch_js)
        self.assertIn('command: "pending_publish.drain"', launch_js)
        self.assertIn('renderLaunchCommandResult("pending-drain-status", "pending-drain-detail", drainResult, request)', launch_js)
        self.assertIn('renderLaunchCommandResult("pipeline-launch-status", "pipeline-launch-detail", result, request)', launch_js)
        self.assertIn("function jsonDetailText", helpers_js)
        self.assertIn("function renderJsonDetail", helpers_js)
        self.assertIn("Read-only structured detail", helpers_js)
        self.assertIn("Backend data JSON", settings_js)
        self.assertIn('renderJsonDetail("pipeline-launch-detail"', launch_js)
        self.assertIn('renderJsonDetail("pending-drain-detail"', launch_js)
        self.assertIn("jsonDetailText({", launch_js)

    def test_ui_polish_error_and_tooltip_guards_are_wired(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        app_js = (static_root / "assets" / "app.js").read_text(encoding="utf-8")
        launch_js = _read_launch_view_asset_bundle(static_root / "assets")
        helpers_js = _read_dom_helpers_asset_bundle(static_root / "assets")
        telemetry_js = "\n".join(
            (static_root / "assets" / name).read_text(encoding="utf-8")
            for name in ("telemetry/gpuProjection.js", "telemetryView.js")
        )
        progress_js = "\n".join(
            (static_root / "assets" / name).read_text(encoding="utf-8")
            for name in (
                "progress/worker.js",
                "progress/csvRerun.js",
                "progress/ffmpegEta.js",
                "progress/evidenceRows.js",
                "progress/liveRun.js",
                "progressView.js",
            )
        )
        app_js += "\n" + (static_root / "assets" / "app" / "refreshCoordinator.js").read_text(encoding="utf-8")
        completed_review_js = _read_completed_review_asset_bundle(static_root / "assets")
        completed_proof_js = "\n".join(
            (static_root / "assets" / name).read_text(encoding="utf-8")
            for name in ("completed/proof/pilotEvidence.js", "completedView.proof.js")
        )

        self.assertIn("function applyDefaultActionTooltips", app_js)
        self.assertIn("function renderTelemetrySafely", app_js)
        self.assertIn('recordLocalUiDiagnostic("telemetry.render"', app_js)
        self.assertIn("function launchCommandRootCauseLines", launch_js)
        self.assertIn("Stack traces are intentionally omitted", launch_js)
        self.assertIn("span.title = `Status:", helpers_js)
        self.assertIn("function telemetryCanvasColors", telemetry_js)
        self.assertIn("const formatters = window.mediaPipelineFormatters || {}", telemetry_js)
        self.assertIn("const formatPercent = typeof formatters.formatPercent", telemetry_js)
        self.assertIn("const formatMemoryMb = typeof formatters.formatMemoryMb", telemetry_js)
        self.assertIn("function telemetryGpuUsagePayload", telemetry_js)
        self.assertIn("desktop_gpu_encoder_usage.v1", telemetry_js)
        self.assertIn("Encoder sessions", telemetry_js)
        self.assertNotIn("#65a7ff", telemetry_js)
        self.assertIn("function progressWorkerPayload", progress_js)
        self.assertIn("const formatters = window.mediaPipelineFormatters || {}", progress_js)
        self.assertIn("const formatProgressValue = typeof formatters.formatProgressValue", progress_js)
        self.assertIn("function progressWorkerRows", progress_js)
        self.assertIn("desktop_worker_progress.v1", progress_js)
        self.assertIn("Worker progress", progress_js)
        self.assertIn("progressWorkerSummaryLine(snapshot, diagnostics)", progress_js)
        self.assertIn("function csvRerunTailEvidence", progress_js)
        self.assertIn("function csvRerunActivityEvidence", progress_js)
        self.assertIn("workerActive", progress_js)
        self.assertIn("CSV rerun:", progress_js)
        self.assertIn("function refreshLiveRunTail", app_js)
        self.assertIn("function csvRerunActivityEvidence", app_js)
        self.assertIn("function renderCsvRerunHomeSummary", app_js)
        self.assertIn("let lastQueue = null;", app_js)
        self.assertIn("renderHomeNextQueue({ ...liveRunContext, queue: lastQueue || {} })", app_js)
        self.assertIn("lastQueue = values.queue;", app_js)
        self.assertIn("renderHomePipelineState(\"csv_rerun_active\")", app_js)
        home_js = "\n".join(
            (static_root / "assets" / name).read_text(encoding="utf-8")
            for name in ("app/home/queueProjection.js", "app/home.js")
        )
        self.assertIn("function renderHomeCsvRerunQueue", home_js)
        self.assertIn("function homeCsvRerunQueueContext", home_js)
        self.assertIn("csvRerunActivityEvidence", home_js)
        self.assertIn("void refreshLiveRunTail(refreshOptions);", app_js)
        self.assertIn('"/api/diagnostics/tail?target=last_stdout_log&max_bytes=65536"', app_js)
        self.assertIn("function progressFfmpegPayload", progress_js)
        self.assertIn("desktop_ffmpeg_progress.v1", progress_js)
        self.assertIn("FFmpeg progress proof", progress_js)
        self.assertIn("function progressEtaPayload", progress_js)
        self.assertIn("desktop_eta.v1", progress_js)
        self.assertIn("No ETA is shown until backend worker progress reports usable percent", progress_js)
        self.assertIn("desktop_validation_state.v1", completed_review_js)
        self.assertIn("Validation state proof", completed_proof_js)
        self.assertIn("does not run ffprobe, hash files, or mark playback accepted", completed_review_js)
        self.assertIn("renderDiagnosticsProgress?.(values.snapshot || lastSnapshot, lastDiagnostics)", app_js)
        self.assertIn("progressWorkerPayload?.(snapshot, diagnostics)", app_js)
        self.assertIn("Executable CSV rerun currently supports scratch-copy staging", launch_js)
        self.assertIn("source files stay untouched unless source-path overwrite is explicitly confirmed", launch_js)
        self.assertIn("Custom negative terms are added to the backend rename planner", html)

    def test_webview_bootstrap_readiness_guards_are_static(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        assets_root = static_root / "assets"
        html = _render_static_index_html(static_root)
        app_js = "\n".join(
            (assets_root / path).read_text(encoding="utf-8")
            for path in ("app/dashboard.js", "app/refreshCoordinator.js", "app.js")
        )
        app_lifecycle_orchestration_js = (assets_root / "app" / "lifecycleOrchestration.js").read_text(encoding="utf-8")
        home_js = (assets_root / "app" / "home.js").read_text(encoding="utf-8")
        launch_js = (assets_root / "launchView.js").read_text(encoding="utf-8")
        pending_view_js = (assets_root / "pendingPublishView.js").read_text(encoding="utf-8")
        queue_js = (assets_root / "queueView.js").read_text(encoding="utf-8")
        queue_summary_js = (assets_root / "queueView.summary.js").read_text(encoding="utf-8")
        large_table_smoke_py = (desktop_root / "tests" / "webview" / "test_webview_browser_large_table_smoke.py").read_text(
            encoding="utf-8"
        )
        settings_launch_smoke_py = (
            desktop_root / "tests" / "webview" / "test_webview_browser_settings_launch_smoke.py"
        ).read_text(encoding="utf-8")

        self.assertLess(html.index('/assets/progressView.js'), html.index('/assets/queueView.summary.js'))
        self.assertLess(html.index('/assets/progressView.js'), html.index('/assets/pendingPublish/details.js'))
        self.assertIn("window.refreshAll = refreshAll;", app_js)
        self.assertIn("window.refreshAllNow = refreshAllNow;", app_js)
        self.assertLess(
            app_lifecycle_orchestration_js.index("initKeyboardShortcuts();"),
            app_lifecycle_orchestration_js.index("await restoreSharedUiPreferences();"),
        )
        self.assertIn('[data-page-panel="launch"] .settings-tab-btn[data-launch-tab]', launch_js)
        self.assertIn("activateLaunchTab(button.dataset.launchTab || \"pipeline\");", launch_js)
        self.assertIn("window.mediaPipelineProgressView?.renderProgressBarsInto?.(...args)", pending_view_js)
        self.assertIn("const progressRenderer = window.mediaPipelineProgressView?.renderProgressBarsInto;", queue_summary_js)
        self.assertIn("const shortenPath = typeof formatters.shortenPath", home_js)
        self.assertIn("const shortenPath = typeof formatters.shortenPath", pending_view_js)
        self.assertIn("const shortenPath = typeof formatters.shortenPath", queue_js)
        self.assertIn("shortenPath,", pending_view_js)
        self.assertIn("shortenPath,", queue_js)
        self.assertIn('document.readyState === "complete"', large_table_smoke_py)
        self.assertIn('typeof window.mediaPipelineProgressView?.renderProgressBarsInto === "function"', large_table_smoke_py)
        self.assertIn('typeof window.refreshAllNow === "function"', large_table_smoke_py)
        self.assertIn('document.readyState === "complete"', settings_launch_smoke_py)
        self.assertIn('typeof window.externalDependencyRows === "function"', settings_launch_smoke_py)
        self.assertIn('typeof window.markSettingsPatchTouched === "function"', settings_launch_smoke_py)
        self.assertIn('typeof window.getCommandHistory === "function"', settings_launch_smoke_py)

    def test_completed_proof_selection_updates_shared_selected_row_state(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        assets_root = desktop_root / "apps" / "desktop" / "webview" / "static" / "assets"

        for asset_name in ["completed/evidence/routeAgreement.js", "completedView.proof.js"]:
            source = (assets_root / asset_name).read_text(encoding="utf-8")
            with self.subTest(asset=asset_name):
                self.assertNotRegex(source, r"(?<!state\.)\bselectedCompletedRowKey\s=")
                self.assertIn("state.selectedCompletedRowKey = item.", source)

    def test_tk_legacy_showerror_callers_route_through_structured_helper(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        package_root = desktop_root / "src" / "mediapipeline" / "desktop"
        offenders: list[str] = []
        for path in package_root.rglob("*.py"):
            rel = path.relative_to(package_root).as_posix()
            source = path.read_text(encoding="utf-8")
            if "messagebox.showerror" not in source:
                continue
            if rel == "widgets.py":
                continue
            offenders.append(rel)
        self.assertEqual(offenders, [])

    def test_webview_panel_types_and_evidence_panels_are_read_only(self) -> None:
        from html.parser import HTMLParser

        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)

        class PanelParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.panel_stack: list[dict[str, object]] = []
                self.panels: list[dict[str, object]] = []

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                attr_map = {key: value or "" for key, value in attrs}
                if tag == "section" and "panel" in attr_map.get("class", "").split():
                    panel = {"type": attr_map.get("data-panel-type"), "buttons": []}
                    self.panel_stack.append(panel)
                    self.panels.append(panel)
                    return
                if tag == "button" and self.panel_stack:
                    if "data-network-future-control" in attr_map and "disabled" in attr_map:
                        return
                    self.panel_stack[-1]["buttons"].append(attr_map)  # type: ignore[index, union-attr]

            def handle_endtag(self, tag: str) -> None:
                if tag == "section" and self.panel_stack:
                    self.panel_stack.pop()

        parser = PanelParser()
        parser.feed(html)
        invalid_types = [panel.get("type") for panel in parser.panels if panel.get("type") not in {"evidence", "interactive", "status"}]
        evidence_buttons = [panel for panel in parser.panels if panel.get("type") == "evidence" and panel.get("buttons")]
        self.assertEqual(invalid_types, [])
        self.assertEqual(evidence_buttons, [])

    def test_webview_page_h1_titles_match_design_reference(self) -> None:
        from html.parser import HTMLParser

        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        expected = {
            "home": "Home",
            "launch": "Launch",
            "live": "Telemetry",
            "metrics": "Metrics",
            "queue": "Queue",
            "completed": "Completed Output",
            "pending": "Pending Publish",
            "rename": "Rename",
            "reports": "Reports",
            "network": "Network Workers",
            "libraries": "Libraries",
            "schedule": "Schedule",
            "settings": "Settings",
            "diagnostics": "Diagnostics",
            "maintenance": "Maintenance",
        }

        class PageTitleParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__(convert_charrefs=True)
                self.current_page = ""
                self.in_h1 = False
                self.buffer: list[str] = []
                self.titles: dict[str, str] = {}

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                attr_map = {key: value or "" for key, value in attrs}
                if tag == "section" and "page" in attr_map.get("class", "").split():
                    self.current_page = attr_map.get("data-page-panel", "")
                if tag == "h1" and self.current_page:
                    self.in_h1 = True
                    self.buffer = []

            def handle_data(self, data: str) -> None:
                if self.in_h1:
                    self.buffer.append(data)

            def handle_endtag(self, tag: str) -> None:
                if tag == "h1" and self.in_h1:
                    self.titles[self.current_page] = "".join(self.buffer).strip()
                    self.in_h1 = False

        parser = PageTitleParser()
        parser.feed(html)
        self.assertEqual(parser.titles, expected)

    def test_settings_subtitle_builder_covers_bdpgs_ocr_path_keys_and_keyword_lists(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        metadata_js = (assets_root / "settingsMetadata.js").read_text(encoding="utf-8")
        subtitle_js = (assets_root / "settingsView.builders.subtitle.js").read_text(encoding="utf-8")
        raw_triage_js = (assets_root / "settingsView.rawTriage.js").read_text(encoding="utf-8")

        self.assertIn('id="settings-subtitle-bdpgs-ocr-tool-path"', html)
        self.assertIn('id="settings-subtitle-bdpgs-ocr-tessdata-path"', html)
        self.assertIn('id="settings-subtitle-vobsub-ocr-tool-path"', html)
        self.assertIn('id="settings-subtitle-bdpgs-ocr-tool-picker-badge"', html)
        self.assertIn('data-path-picker-target="settings.subtitle.bdpgs_ocr_tool_path"', html)
        self.assertIn('id="settings-subtitle-bdpgs-tessdata-picker-badge"', html)
        self.assertIn('data-path-picker-target="settings.subtitle.bdpgs_ocr_tessdata_path"', html)
        self.assertIn('id="settings-subtitle-vobsub-ocr-tool-picker-badge"', html)
        self.assertIn('data-path-picker-target="settings.subtitle.vobsub_ocr_tool_path"', html)
        self.assertIn('id="settings-subtitle-sdh-keywords"', html)
        self.assertIn('id="settings-subtitle-supplemental-keywords"', html)
        self.assertNotIn("settings-subtitle-bdpgs-ocr-browse", html)
        self.assertNotIn("settings-subtitle-vobsub-ocr-browse", html)
        self.assertIn('["BdpgsOcrToolPath", "settings-subtitle-bdpgs-ocr-tool-path", "text"]', metadata_js)
        self.assertIn('["BdpgsOcrTessdataPath", "settings-subtitle-bdpgs-ocr-tessdata-path", "text"]', metadata_js)
        self.assertIn('["VobSubOcrToolPath", "settings-subtitle-vobsub-ocr-tool-path", "text"]', metadata_js)
        self.assertIn('["SubSDHTitleKeywords", "settings-subtitle-sdh-keywords", "list"]', metadata_js)
        self.assertIn('["SubSupplementalKeywords", "settings-subtitle-supplemental-keywords", "list"]', metadata_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-bdpgs-ocr-tool-path", "BdpgsOcrToolPath", "text"', subtitle_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-bdpgs-ocr-tessdata-path", "BdpgsOcrTessdataPath", "text"', subtitle_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-vobsub-ocr-tool-path", "VobSubOcrToolPath", "text"', subtitle_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-sdh-keywords", "SubSDHTitleKeywords", "list"', subtitle_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-supplemental-keywords", "SubSupplementalKeywords", "list"', subtitle_js)
        self.assertIn('if (kind === "text") return String(element.value || "").trim();', subtitle_js)
        self.assertIn('if (kind === "list") return parseSettingsListText(element.value);', subtitle_js)
        self.assertIn("WebView does not browse arbitrary paths, resolve paths, or run OCR.", subtitle_js)
        self.assertIn("WebView does not classify subtitle tracks.", subtitle_js)
        self.assertIn("are covered by the Subtitle builder", raw_triage_js)
        self.assertIn("subtitle keyword builder coverage", raw_triage_js)
        self.assertIn("backend subtitle classification remains authoritative", raw_triage_js)
        self.assertIn("do not add a frontend-owned path picker", raw_triage_js)
        self.assertIn("Any folder picker must be backend-owned and allowlisted", raw_triage_js)

    def test_settings_file_safety_path_browse_is_backend_owned_staging(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        settings_js = _read_settings_asset_bundle(assets_root)
        app_js = "\n".join(
            (assets_root / name).read_text(encoding="utf-8")
            for name in ("app.js", "app/refreshCoordinator.js", "app/lifecycleOrchestration.js")
        )
        settings_history_js = (assets_root / "settingsCommandHistory.js").read_text(encoding="utf-8")

        for key, input_id in [
            ("SourceMovies", "settings-file-safety-source-movies"),
            ("SourceTV", "settings-file-safety-source-tv"),
            ("Outsource", "settings-file-safety-outsource"),
            ("LocalBase", "settings-file-safety-local-base"),
        ]:
            with self.subTest(key=key):
                self.assertIn(f'data-settings-path-key="{key}"', html)
                self.assertIn(f'data-settings-path-input="{input_id}"', html)
                self.assertIn(f'data-path-picker-input="{input_id}"', html)
                self.assertIn(f'id="{input_id}-picker-badge"', html)
                self.assertIn(f'data-path-picker-target="settings.file_safety.{key}"', html)
        self.assertIn('id="settings-file-safety-watch-roots-picker-badge"', html)
        self.assertIn('data-path-picker-target="settings.file_safety.WatchFolderRoots"', html)
        self.assertIn('data-path-picker-write="append-list"', html)
        self.assertIn('"/api/settings/browse-path"', settings_js)
        self.assertIn('selection_mode: "folder"', settings_js)
        self.assertIn("writes_config", settings_js)
        self.assertIn("stages_only", settings_js)
        self.assertIn("Use Save Settings to review and write the prepared File Safety change.", settings_js)
        self.assertIn("It cannot save settings, launch work, rewrite queue state, publish, rename, delete, or touch media files.", settings_js)
        self.assertIn("[data-settings-path-key]", app_js)
        self.assertIn('command === "settings.browse_path"', settings_history_js)

    def test_shared_path_picker_badge_helper_is_backend_owned_staging(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        path_picker_js = (static_root / "assets" / "pathPicker.js").read_text(encoding="utf-8")

        self.assertIn('/assets/pathPicker.js', html)
        _assert_namespace_export(self, path_picker_js, "mediaPipelinePathPicker", "browsePath")
        _assert_namespace_export(self, path_picker_js, "mediaPipelinePathPicker", "inputForButton")
        self.assertIn("[data-path-picker-target]", path_picker_js)
        self.assertIn('apiPost("/api/path-picker/browse"', path_picker_js)
        self.assertIn("pathPickerInput", path_picker_js)
        self.assertIn("pathPickerMode", path_picker_js)
        self.assertIn("pathPickerFilter", path_picker_js)
        self.assertIn("pathPickerStatus", path_picker_js)
        self.assertIn("pathPickerWrite", path_picker_js)
        self.assertIn("path-picker:staged", path_picker_js)
        self.assertIn("command: \"path_picker.browse\"", path_picker_js)
        self.assertNotIn("window.browsePath =", path_picker_js)
        self.assertNotIn("confirm_save", path_picker_js)

    def test_settings_tv_library_folder_panel_explains_backend_owned_keys(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        file_safety_js = (assets_root / "settingsView.builders.file_safety.js").read_text(encoding="utf-8")

        self.assertIn("TV Library Folders", html)
        self.assertIn('id="settings-file-safety-aggressive-episode"', html)
        self.assertIn('id="settings-file-safety-create-tv-subfolder"', html)
        self.assertIn('id="settings-tv-library-folder-status"', html)
        self.assertIn('id="settings-tv-library-folder-evidence"', html)
        self.assertIn("settings-tv-library-panel", html)
        self.assertIn("renderTvLibraryFolderEvidence", file_safety_js)
        self.assertIn("folder season hints and loose anime/import filename patterns", file_safety_js)
        self.assertIn("backend Save and engine naming/publish behavior remain authoritative", file_safety_js)

    def test_web_command_feedback_preserves_backend_warnings_and_errors(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static" / "assets"
        command_history_js = _read_command_history_asset_bundle(static_root)
        diagnostics_bridge_js = (static_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        queue_view_js = _read_queue_asset_bundle(static_root)
        completed_view_js = _read_completed_asset_bundle(static_root)
        rename_view_js = _read_rename_asset_bundle(static_root)
        rename_history_view_js = (static_root / "renameHistoryView.js").read_text(encoding="utf-8")
        maintenance_view_js = "\n".join(
            (static_root / asset_name).read_text(encoding="utf-8")
            for asset_name in (
                "maintenance/changeLedger.js",
                "maintenance/health.js",
                "maintenance/dryRunReadiness.js",
                "maintenance/releaseCommands.js",
                "maintenanceView.js",
            )
        )
        settings_command_history_js = (static_root / "settingsCommandHistory.js").read_text(encoding="utf-8")
        pending_publish_diagnostics_js = (static_root / "pendingPublishView.diagnostics.js").read_text(encoding="utf-8")
        pending_publish_drain_js = (static_root / "pendingPublishView.drain.js").read_text(encoding="utf-8")
        pending_publish_view_js = (static_root / "pendingPublishView.js").read_text(encoding="utf-8")
        launch_history_view_js = (static_root / "launchHistoryView.js").read_text(encoding="utf-8")
        launch_preflight_view_js = (static_root / "launchView.preflight.js").read_text(encoding="utf-8")
        diagnostics_view_js = _read_diagnostics_asset_bundle(static_root)
        reports_view_js = (static_root / "reportsView.js").read_text(encoding="utf-8")
        reports_shell_js = (static_root / "reports" / "shell.js").read_text(encoding="utf-8")
        network_view_js = _read_network_asset_bundle(static_root)
        app_js = (static_root / "app.js").read_text(encoding="utf-8")

        self.assertIn("const COMMAND_RESULT_LIST_LIMIT = 5", command_history_js)
        self.assertIn("const COMMAND_RESULT_ITEM_CHARS = 240", command_history_js)
        self.assertIn("function commandResultDisplayMessage", command_history_js)
        self.assertIn("function commandResultFeedbackLines", command_history_js)
        self.assertIn("function commandHistoryCommandText", command_history_js)
        self.assertIn("function commandHistoryCompactEvidenceLine", command_history_js)
        self.assertIn("function commandHistoryDiagnosticLine", command_history_js)
        self.assertIn("function compactCommandHistoryEntries", command_history_js)
        self.assertIn("function compactCommandHistoryBlockText", command_history_js)
        self.assertIn("function renderCompactCommandHistoryBlock", command_history_js)
        self.assertIn("owner=${commandHistoryOwnerPage(item)}", command_history_js)
        self.assertIn("issue=${commandHistoryIssueLevel(item)}", command_history_js)
        self.assertIn("window.commandHistoryCompactEvidenceLine = commandHistoryCompactEvidenceLine", command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "renderCompactCommandHistoryBlock")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryDiagnosticLine")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryCommandText")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryOwnerPage")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryIssueLevel")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistorySuggestedAction")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "getSelectedCommandEntry")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryRowKey")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "selectCommandEntry")
        self.assertNotIn("window.commandHistoryCommandText = commandHistoryCommandText", command_history_js)
        self.assertNotIn("window.commandHistorySuggestedAction = commandHistorySuggestedAction", command_history_js)
        self.assertNotIn("window.commandHistoryOwnerPage = commandHistoryOwnerPage", command_history_js)
        self.assertNotIn("window.commandHistoryIssueLevel = commandHistoryIssueLevel", command_history_js)
        self.assertNotIn("window.getSelectedCommandEntry = getSelectedCommandEntry", command_history_js)
        self.assertNotIn("window.commandHistoryRowKey = commandHistoryRowKey", command_history_js)
        self.assertNotIn("window.selectCommandEntry = selectCommandEntry", command_history_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", settings_command_history_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", rename_history_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", launch_history_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", pending_publish_diagnostics_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", pending_publish_drain_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", queue_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", completed_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", diagnostics_view_js)
        self.assertIn(
            'commandHistoryCompactEvidenceLine: typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null',
            reports_view_js,
        )
        self.assertIn("commandHistoryCompactEvidenceLine(entry", reports_shell_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", network_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(item", maintenance_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", launch_preflight_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", app_js)
        self.assertIn("renderCompactCommandHistoryBlock({", settings_command_history_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", launch_history_view_js)
        self.assertIn("renderCompactCommandHistoryBlock({", reports_shell_js)
        self.assertIn("renderCompactCommandHistoryBlock({", maintenance_view_js)
        self.assertIn("renderCompactCommandHistoryBlock({", pending_publish_drain_js)
        self.assertIn("renderCompactCommandHistoryBlock: window.mediaPipelineCommandHistory?.renderCompactCommandHistoryBlock", pending_publish_view_js)
        self.assertIn("function commandHistoryIsPendingPublishCommand", command_history_js)
        self.assertIn("function commandHistoryPendingPublishCommandKind", command_history_js)
        self.assertIn("function commandHistoryPendingPublishSuggestedAction", command_history_js)
        self.assertIn("function commandHistoryPendingPublishDataLines", command_history_js)
        self.assertIn("function commandHistoryPendingPublishDigestLines", command_history_js)
        self.assertIn("function commandHistoryPendingPublishEntries", command_history_js)
        self.assertIn("Pending Publish command digest:", command_history_js)
        self.assertIn("commandHistoryPendingPublishDigestLines(commandHistory)", command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryPendingPublishDigestLines")
        self.assertIn("Pending Publish command triage:", command_history_js)
        self.assertIn("Command kind: ${kind}", command_history_js)
        self.assertIn("Read-first order: Last Stderr -> Latest Failure Report -> Pending Publish state.", command_history_js)
        self.assertIn("Open-next order: Pending Publish -> Run Logs -> State Folder", command_history_js)
        self.assertIn("Do not drain yet. Inspect blocker rows in Pending Publish", command_history_js)
        self.assertIn("Treat the drain as failed or incomplete. Refresh Pending Publish", command_history_js)
        self.assertIn("Mutation guardrail: command history never repairs, drains, rewrites, moves, deletes, or publishes files by itself.", command_history_js)
        self.assertIn("function requestCommandDiagnosticsAction", command_history_js)
        self.assertIn("appendDiagnosticsBridgeGroupedButtons(container, actions", command_history_js)
        self.assertIn('datasetPrefix: "commandDiagnostics"', command_history_js)
        self.assertIn('datasetPrefix: "diagnosticsCommandDrilldown"', command_history_js)
        self.assertIn("renderDiagnosticsCommandDrilldown(commandHistory)", command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "renderDiagnosticsCommandDrilldown")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "renderCommandDiagnosticsEvidence")
        self.assertNotIn("window.renderCommandDiagnosticsEvidence = renderCommandDiagnosticsEvidence", command_history_js)
        self.assertIn("function mergeCommandHistory", command_history_js)
        self.assertIn("local: true", command_history_js)
        self.assertIn("raw: payload", command_history_js)
        self.assertIn("raw: entry", command_history_js)
        self.assertIn("commandResultList(payload.warnings)", command_history_js)
        self.assertIn("commandResultList(payload.errors)", command_history_js)
        self.assertIn("commandResultList(entry.warnings)", command_history_js)
        self.assertIn("commandResultList(entry.errors)", command_history_js)
        self.assertIn('Errors: ${errors.join(" | ")}', command_history_js)
        self.assertIn('Warnings: ${warnings.join(" | ")}', command_history_js)
        self.assertIn('row.dataset.status = ["error", "blocked"].includes(issue) ? "blocked" : issue === "warning" ? "warning" : item.ok ? "match" : "blocked"', command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandResultDisplayMessage")
        self.assertIn("window.mediaPipelineDiagnosticsBridge", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgePrimaryAction", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeSetTailTarget", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeActionGroups", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeReviewAction", diagnostics_bridge_js)
        self.assertIn("function appendDiagnosticsBridgeButton", diagnostics_bridge_js)
        self.assertIn("Review in Diagnostics", diagnostics_bridge_js)
        self.assertIn("bridge selection does not read files, open paths, mutate queue state, or publish outputs", diagnostics_bridge_js)
        self.assertIn("window.mediaPipelineDiagnosticsView?.setDiagnosticsTailTarget", diagnostics_bridge_js)
        self.assertIn("window.mediaPipelineDiagnosticsTailView?.setDiagnosticsTailTarget", diagnostics_bridge_js)
        self.assertNotIn('typeof window.setDiagnosticsTailTarget === "function"', diagnostics_bridge_js)
        _assert_namespace_export(self, diagnostics_bridge_js, "mediaPipelineDiagnosticsBridge", "diagnosticsBridgeActions")
        self.assertNotIn("window.diagnosticsBridgeActions = diagnosticsBridgeActions", diagnostics_bridge_js)

        self.assertIsNotNone(
            re.search(
                r'const result = await apiPost\("/api/queue/open".*?appendCommandResult\(result\);',
                queue_view_js,
                re.S,
            )
        )
        self.assertIsNotNone(
            re.search(
                r'const result = await apiPost\("/api/completed/open".*?appendCommandResult\(result\);',
                completed_view_js,
                re.S,
            )
        )
        self.assertIsNotNone(
            re.search(
                r'const result = await apiPost\("/api/rename/apply".*?appendCommandResult\(visibleResult\);',
                rename_view_js,
                re.S,
            )
        )
        self.assertIn("visibleResult = { ...result, request };", rename_view_js)
        self.assertIn("renderRenameApplyResult(visibleResult);", rename_view_js)
        self.assertIn("function renderRenamePipelineHandoff", rename_view_js)
        self.assertIn("Rename-to-pipeline handoff:", rename_view_js)
        self.assertIn("renaming changes filenames only", rename_view_js)
        self.assertIn('renameConfigValue(config, "DeleteSourceAfterProcessing", "false")', rename_view_js)
        self.assertNotIn("DeleteOriginalAfterProcessing", rename_view_js)
        self.assertIn("request.selected_sources = rowsToApply.map((row) => row.source);", rename_view_js)
        self.assertIn("Apply scope: checked rows are required and are sent as selected_sources", rename_view_js)
        self.assertGreaterEqual(
            maintenance_view_js.count('lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));'),
            2,
        )

    def test_web_tables_share_accessible_selection_helpers(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        dom_helpers_js = _read_dom_helpers_asset_bundle(assets_root)
        styles_css = resolved_css_asset_bundle(assets_root)
        queue_view_js = _read_queue_asset_bundle(assets_root)
        completed_view_evidence_js = _read_completed_evidence_asset_bundle(assets_root)
        completed_view_review_js = _read_completed_review_asset_bundle(assets_root)
        completed_view_js = _read_completed_asset_bundle(assets_root)
        pending_view_drain_js = (assets_root / "pendingPublishView.drain.js").read_text(encoding="utf-8")
        pending_view_confidence_js = "\n".join((
            (assets_root / "pendingPublish" / "confidence" / "postDrainTrust.js").read_text(encoding="utf-8"),
            (assets_root / "pendingPublishView.confidence.js").read_text(encoding="utf-8"),
        ))
        pending_view_js = _read_pending_publish_asset_bundle(assets_root)
        rename_view_js = _read_rename_asset_bundle(assets_root)
        command_history_js = _read_command_history_asset_bundle(assets_root)
        diagnostics_bridge_js = (assets_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        reports_audit_view_js = (assets_root / "reports" / "auditView.js").read_text(encoding="utf-8")
        reports_failure_view_js = (assets_root / "reports" / "failureView.js").read_text(encoding="utf-8")
        diagnostics_view_js = _read_diagnostics_asset_bundle(assets_root)
        diagnostics_state_js = (assets_root / "diagnosticsStateSummaryView.js").read_text(encoding="utf-8")
        network_view_js = _read_network_asset_bundle(assets_root)
        contract_view_js = (assets_root / "contractView.js").read_text(encoding="utf-8")
        launch_view_risk_js = _read_launch_risk_asset_bundle(assets_root)
        launch_view_scope_js = (assets_root / "launchView.scope.js").read_text(encoding="utf-8")
        launch_view_preflight_js = (assets_root / "launchView.preflight.js").read_text(encoding="utf-8")
        app_js = "\n".join(
            (assets_root / name).read_text(encoding="utf-8")
            for name in ("app.js", "app/refreshCoordinator.js", "app/lifecycleOrchestration.js")
        )

        for node_id in [
            "command-table-legend",
            "queue-table-legend",
            "queue-excluded-table-legend",
            "queue-backend-scope-legend",
            "queue-launch-decision-legend",
            "completed-table-legend",
            "completed-history-table-legend",
            "completed-size-evidence-legend",
            "completed-pending-proof-legend",
            "publish-reconciliation-legend",
            "completed-output-acceptance-legend",
            "completed-route-agreement-legend",
            "pending-table-legend",
            "pending-backend-scope-legend",
            "pending-drain-decision-legend",
            "rename-table-legend",
            "failure-table-legend",
            "audit-preview-table-legend",
            "network-worker-table-legend",
            "diagnostics-first-response-legend",
            "diagnostics-state-summary-table-legend",
            "diagnostics-owner-handoff-legend",
            "diagnostics-log-table-legend",
            "active-job-table-legend",
            "diagnostics-command-resolution-legend",
            "launch-settings-intent-legend",
            "launch-scope-reconciliation-legend",
            "launch-start-decision-legend",
            "launch-backend-preflight-legend",
            "api-contract-safety-legend",
            "api-contract-table-legend",
        ]:
            self.assertIn(f'id="{node_id}"', html)
        self.assertIn('id="queue-table-legend" class="note table-legend" hidden aria-hidden="true"></p>', html)

        self.assertIn("function makeRowSelectable", dom_helpers_js)
        self.assertIn('row.dataset.selectableRow = "true"', dom_helpers_js)
        self.assertIn('row.setAttribute("aria-selected"', dom_helpers_js)
        self.assertIn('event.key === "ArrowDown"', dom_helpers_js)
        self.assertIn('event.key === "ArrowUp"', dom_helpers_js)
        self.assertIn("options.scrollOnRender === true", dom_helpers_js)
        self.assertIn("function updateTableStatusLegend", dom_helpers_js)
        self.assertIn("function tableStatusLegendText", dom_helpers_js)
        self.assertIn("function filterResultSummaryLines", dom_helpers_js)
        self.assertIn("function countRowsByStatus", dom_helpers_js)
        self.assertIn("function filterRowsByStatus", dom_helpers_js)
        self.assertIn("function filterRowsByInvestigation", dom_helpers_js)
        self.assertIn("function captureScrollablePositions", dom_helpers_js)
        self.assertIn("function restoreScrollablePositions", dom_helpers_js)
        self.assertIn("function tableStatusMatchesFilter", dom_helpers_js)
        self.assertIn("function tableStatusFilterLabel", dom_helpers_js)
        self.assertIn("function tableInvestigationFilterLabel", dom_helpers_js)
        self.assertIn("function reviewFlagExplanationLines", dom_helpers_js)
        self.assertIn("expected output proof is missing", dom_helpers_js)
        self.assertIn("translate already-loaded backend markers", dom_helpers_js)
        self.assertIn("function selectedRowDetailDrawerLines", dom_helpers_js)
        self.assertIn("Hidden review rows:", dom_helpers_js)
        self.assertIn("filters are display-only", dom_helpers_js)
        self.assertIn("window.makeRowSelectable = makeRowSelectable", dom_helpers_js)
        self.assertIn("window.filterRowsByStatus = filterRowsByStatus", dom_helpers_js)
        self.assertIn("window.filterRowsByInvestigation = filterRowsByInvestigation", dom_helpers_js)
        _assert_namespace_export(self, dom_helpers_js, "mediaPipelineDom", "captureScrollablePositions")
        _assert_namespace_export(self, dom_helpers_js, "mediaPipelineDom", "restoreScrollablePositions")
        _assert_namespace_export(self, dom_helpers_js, "mediaPipelineDom", "filterResultSummaryLines")
        _assert_namespace_export(self, dom_helpers_js, "mediaPipelineDom", "reviewFlagExplanationLines")
        _assert_namespace_export(self, dom_helpers_js, "mediaPipelineDom", "selectedRowDetailDrawerLines")
        _assert_namespace_export(self, diagnostics_bridge_js, "mediaPipelineDiagnosticsBridge", "diagnosticsBridgeActions")
        self.assertIn("function diagnosticsOwnerHandoffRows", diagnostics_view_js)
        self.assertIn("function diagnosticsCompletedFinalTrustStepForRow", diagnostics_view_js)
        self.assertIn("function diagnosticsCompletedFinalTrustLines", diagnostics_view_js)
        self.assertIn("function diagnosticsCompletedPolicyReconciliationLines", diagnostics_view_js)
        self.assertIn("function navigateDiagnosticsOwnerHandoffRow", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsOwnerHandoff", diagnostics_view_js)
        self.assertIn("Completed final trust handoff:", diagnostics_view_js)
        self.assertIn("Completed saved-policy reconciliation handoff:", diagnostics_view_js)
        self.assertIn("Completed > Selected Pilot Evidence Packet > Saved policy reconciliation", diagnostics_view_js)
        self.assertIn("function diagnosticsSampleValidationComparisonLines", diagnostics_view_js)
        self.assertIn("Sample Validation context for this Diagnostics handoff:", diagnostics_view_js)
        self.assertIn('step: "2. Output and sidecar on disk"', diagnostics_view_js)
        self.assertIn("Final trust step: ${step.step}", diagnostics_view_js)
        self.assertIn("After Go To Owner Row, read Completed > Final Output Trust Walkthrough", diagnostics_view_js)
        self.assertIn("completedView.selectCompletedFinalTrustStep(item.completedFinalTrust.step)", diagnostics_view_js)
        self.assertIn("window.mediaPipelineCompletedView?.completedReviewRows", diagnostics_view_js)
        self.assertNotIn("window.selectCompletedFinalTrustStep(item.completedFinalTrust.step)", diagnostics_view_js)
        self.assertNotIn("window.completedReviewRows", diagnostics_view_js)
        self.assertIn("Selected Completed > Final Output Trust Walkthrough step", diagnostics_view_js)
        _assert_namespace_export(self, diagnostics_view_js, "mediaPipelineDiagnosticsView", "navigateDiagnosticsOwnerHandoffRow")
        _assert_namespace_export(self, diagnostics_view_js, "mediaPipelineDiagnosticsView", "renderDiagnosticsOwnerHandoff")
        self.assertIn("Read/open boundary: diagnostics targets are backend allowlist identifiers", diagnostics_view_js)
        self.assertIn("Row file/folder opens belong to the owning page and require row_key plus target only.", diagnostics_view_js)
        self.assertIn("Go To Owner Row is local UI selection over already-loaded data", diagnostics_view_js)
        self.assertIn("Diagnostics artifact JSON", diagnostics_state_js)
        self.assertIn("Diagnostics triage JSON", diagnostics_state_js)
        self.assertIn("jsonDetailText({", diagnostics_state_js)
        self.assertIn("renderDiagnosticsOwnerHandoffFn({", app_js)
        self.assertIn("sampleValidation: values[\"sample validation\"]", app_js)
        self.assertIn("function renderBrandVersion", app_js)
        self.assertIn("renderBrandVersion();", app_js)
        self.assertIn("function keyboardShortcutRegistry", app_js)
        self.assertIn("function focusActivePageSearch", app_js)
        self.assertIn("function clearActivePageFilters", app_js)
        self.assertIn("function moveActivePageSelection", app_js)
        self.assertIn("function _movePanelByStep", app_js)
        self.assertIn("pcb-btn-move-up", app_js)
        self.assertIn("pcb-btn-move-down", app_js)
        self.assertIn("panel-layout-moved", styles_css)
        self.assertIn("@keyframes panel-hold-pulse", styles_css)
        self.assertIn("function focusActivePageDetail", app_js)
        self.assertIn("Read-only shortcuts. They navigate, refresh, filter, focus, or select rows", app_js)
        self.assertIn('key: "/"', app_js)
        self.assertIn('key: "c"', app_js)
        self.assertIn('key: "j"', app_js)
        self.assertIn('key: "k"', app_js)
        self.assertIn('key: "d"', app_js)
        self.assertIn("startup HTML/assets are a separate shell bootstrap surface", contract_view_js)
        self.assertIn("/ and /assets/* are served for startup", contract_view_js)
        self.assertIn("Route contract JSON", contract_view_js)
        self.assertIn("jsonDetailText({", contract_view_js)
        self.assertIn("formats already-loaded route data only", contract_view_js)
        self.assertNotIn("Only /api/health is public; all operator routes stay token-protected.", contract_view_js)
        self.assertIn("window.mediaPipelineDom?.selectedRowDetailDrawerLines", queue_view_js)
        self.assertIn("Queue selected-row detail", queue_view_js)
        self.assertIn("reviewFlagExplanationLines(reviewFlags", queue_view_js)
        self.assertIn("No Queue review flags were reported for this row.", queue_view_js)
        self.assertIn("window.mediaPipelineDom?.selectedRowDetailDrawerLines", completed_view_js)
        self.assertIn("Completed selected-row detail", completed_view_js)
        self.assertIn("reviewFlagExplanationLines(reviewMarkers", completed_view_review_js)
        self.assertIn("No Completed review flags or consistency issues were reported for this row.", completed_view_review_js)
        self.assertIn(".inline-actions", styles_css)
        self.assertIn('tr[data-selectable-row="true"]:focus-visible td', styles_css)
        self.assertIn('tr[data-status="failed"] td', styles_css)
        self.assertIn(".output-overview-section-current", styles_css)
        self.assertIn(".output-overview-section-history", styles_css)
        self.assertIn('.completed-table tr[data-status="changed"] td', styles_css)

        for view_js, legend_id in [
            (queue_view_js, "queue-excluded-table-legend"),
            (queue_view_js, "queue-backend-scope-legend"),
            (queue_view_js, "queue-launch-decision-legend"),
            (completed_view_js, "completed-table-legend"),
            (completed_view_js, "completed-history-table-legend"),
            (completed_view_review_js, "completed-size-evidence-legend"),
            (completed_view_evidence_js, "completed-pending-proof-legend"),
            (completed_view_evidence_js, "publish-reconciliation-legend"),
            (completed_view_evidence_js, "completed-output-acceptance-legend"),
            (completed_view_evidence_js, "completed-route-agreement-legend"),
            (pending_view_js, "pending-table-legend"),
            (pending_view_drain_js, "pending-backend-scope-legend"),
            (pending_view_confidence_js, "pending-drain-decision-legend"),
            (rename_view_js, "rename-table-legend"),
            (command_history_js, "command-table-legend"),
            (reports_failure_view_js, "failure-table-legend"),
            (reports_audit_view_js, "audit-preview-table-legend"),
            (network_view_js, "network-worker-table-legend"),
            (diagnostics_view_js, "diagnostics-first-response-legend"),
            (diagnostics_state_js, "diagnostics-state-summary-table-legend"),
            (diagnostics_view_js, "diagnostics-owner-handoff-legend"),
            (diagnostics_view_js, "diagnostics-log-table-legend"),
            (diagnostics_view_js, "active-job-table-legend"),
            (command_history_js, "diagnostics-command-resolution-legend"),
            (launch_view_risk_js, "launch-settings-intent-legend"),
            (launch_view_scope_js, "launch-scope-reconciliation-legend"),
            (launch_view_scope_js, "launch-start-decision-legend"),
            (launch_view_preflight_js, "launch-backend-preflight-legend"),
            (contract_view_js, "api-contract-safety-legend"),
            (contract_view_js, "api-contract-table-legend"),
        ]:
            self.assertIn("makeRowSelectable(row", view_js)
            if f'updateTableStatusLegend("{legend_id}"' not in view_js:
                self.assertIn(f'legendId: "{legend_id}"', view_js)
                self.assertIn("updateTableStatusLegend(", view_js)
            else:
                self.assertIn(f'updateTableStatusLegend("{legend_id}"', view_js)

    def test_queue_file_settings_drawer_is_late_bound(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        assets_root = desktop_root / "apps" / "desktop" / "webview" / "static" / "assets"
        queue_table_js = (assets_root / "queue" / "table.js").read_text(encoding="utf-8")
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)

        table_factory_match = re.search(
            r"function createQueueTableModule\(\{(?P<params>.*?)\} = \{\}\)",
            queue_table_js,
            re.S,
        )
        self.assertIsNotNone(table_factory_match)
        self.assertNotIn("openFileSettingsDrawer", table_factory_match.group("params"))
        self.assertNotIn("createQueueFileSettingsButton(item, openFileSettingsDrawer)", queue_table_js)
        self.assertNotIn("appendQueueFileSettingsButton(cell, item, openFileSettingsDrawer)", queue_table_js)
        self.assertIn("let openFileSettingsDrawer = function () {};", queue_table_js)
        self.assertIn("openFileSettingsDrawer(item, { trigger: button });", queue_table_js)
        self.assertIn("setOpenFileSettingsDrawer: (handler) => {", queue_table_js)
        self.assertNotIn("openFileSettingsDrawer: typeof openFileSettingsDrawer", queue_view_js)
        self.assertIn('window.__queueSetFileDrawer = typeof _queueTable.setOpenFileSettingsDrawer === "function"', queue_view_js)
        self.assertIn("? _queueTable.setOpenFileSettingsDrawer.bind(_queueTable)", queue_view_js)
        self.assertIn("try {\n    if (typeof window.__queueSetFileDrawer === \"function\")", queue_view_js)
        self.assertIn("window.__queueSetFileDrawer(openFileSettingsDrawer);", queue_view_js)
        self.assertIn("finally {\n    delete window.__queueSetFileDrawer;", queue_view_js)
        self.assertIn("await refreshAllFn();", queue_view_js)

    def test_queue_priority_clear_all_uses_manifest_clear_route(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        assets_root = desktop_root / "apps" / "desktop" / "webview" / "static" / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_table_js = (assets_root / "queue" / "table.js").read_text(encoding="utf-8")

        self.assertIn('async function clearPriorityManifest()', queue_view_js)
        self.assertIn("let inFlight = false;", queue_view_js)
        self.assertIn("function beginCommand(message = \"\")", queue_view_js)
        self.assertIn("function endCommand(seq)", queue_view_js)
        self.assertIn("if (inFlight)", queue_view_js)
        self.assertIn('apiPost("/api/queue/priority", { clear_all: true })', queue_view_js)
        self.assertIn('wire("queue-priority-clear-all-btn", clearPriorityManifest);', queue_view_js)
        self.assertIn('return Boolean(item.is_priority) && manifestLevel === "normal" ? "fs" : manifestLevel;', queue_table_js)
        self.assertIn('const labels = { high: "High", low: "Low", hold: "Hold", fs: "FS" };', queue_table_js)
        self.assertNotIn('Cleared priority manifest for ${items.length} row(s).', queue_view_js)
        refresh_snippet = "if (result?.ok) await refreshAll();"
        send_block = queue_view_js[
            queue_view_js.index("async function sendPriority(") :
            queue_view_js.index("async function sendPriorityBulk(")
        ]
        bulk_block = queue_view_js[
            queue_view_js.index("async function sendPriorityBulk(") :
            queue_view_js.index("async function clearPriorityManifest(")
        ]
        clear_block = queue_view_js[
            queue_view_js.index("async function clearPriorityManifest(") :
            queue_view_js.index("function initQueuePriorityToolbar()")
        ]
        self.assertIn("function applyDisplayedPriorityUpdates(items)", queue_view_js)
        self.assertIn("function clearDisplayedPriorityManifest()", queue_view_js)
        self.assertIn("manifest_priority_level: level", queue_view_js)
        self.assertIn("priority_visible_count: rows.filter(rowHasVisibleMarker).length", queue_view_js)
        self.assertIn("renderRows();", queue_view_js)
        self.assertIn("if (result?.ok) applyDisplayedPriorityUpdates([{ path, level }]);", send_block)
        self.assertIn("if (result?.ok) applyDisplayedPriorityUpdates(items);", bulk_block)
        self.assertIn("if (result?.ok) clearDisplayedPriorityManifest();", clear_block)
        self.assertLess(send_block.index("applyDisplayedPriorityUpdates"), send_block.index(refresh_snippet))
        self.assertLess(bulk_block.index("applyDisplayedPriorityUpdates"), bulk_block.index(refresh_snippet))
        self.assertLess(clear_block.index("clearDisplayedPriorityManifest();"), clear_block.index(refresh_snippet))
        self.assertIn(refresh_snippet, send_block)
        self.assertIn(refresh_snippet, bulk_block)
        self.assertIn(refresh_snippet, clear_block)

    def test_queue_manual_order_controls_write_manifest_positions(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_table_js = (assets_root / "queue" / "table.js").read_text(encoding="utf-8")
        queue_css = _read_queue_css(assets_root)

        for element_id in [
            "queue-manual-save-order-btn",
            "queue-manual-discard-order-btn",
            "queue-manual-move-top-btn",
            "queue-manual-move-up-btn",
            "queue-manual-move-down-btn",
            "queue-manual-move-bottom-btn",
            "queue-manual-order-status",
            "queue-table-pagination",
            "queue-table-page-status",
            "queue-page-prev-btn",
            "queue-page-next-btn",
        ]:
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, html)

        self.assertIn('<pre id="queue-filter-summary" class="prose-block queue-filter-summary" hidden aria-hidden="true">', html)
        self.assertIn("const QUEUE_RENDER_LIMIT = 250;", queue_view_js)
        self.assertIn("function updateQueuePaginationControls(rowCount, pageStart, renderedCount)", queue_view_js)
        self.assertIn("function moveQueueTablePage(delta)", queue_view_js)
        self.assertIn("function setQueueFilterSummary(lines)", queue_view_js)
        self.assertIn("function queueManualOrderPositionItems()", queue_view_js)
        self.assertIn("let queueManualOrderLoadedKeys = [];", queue_view_js)
        self.assertIn("let queueManualOrderDraftDirty = false;", queue_view_js)
        self.assertIn("function resetQueueManualOrderLoadedKeys(rows = state.rows)", queue_view_js)
        self.assertIn("function syncQueueManualOrderDraftDirty()", queue_view_js)
        self.assertIn("position: index + 1", queue_view_js)
        self.assertIn('apiPost("/api/queue/priority", { items })', queue_view_js)
        self.assertIn("if (!syncQueueManualOrderDraftDirty())", queue_view_js)
        self.assertIn('queueManualOrderStatus("No staged manual-order changes to save.");', queue_view_js)
        self.assertIn("Staged manual order for ${queueManualOrderPhaseLabel(context.phase)}", queue_view_js)
        self.assertIn("renderQueueRows({ preservePage: true });", queue_view_js)
        self.assertIn("function discardQueueManualOrderDraft()", queue_view_js)
        self.assertIn("function restoreQueueManualOrderLoadedOrder()", queue_view_js)
        self.assertIn('wire("queue-manual-move-up-btn", () => moveQueueManualOrder("up"));', queue_view_js)
        self.assertIn('wire("queue-manual-discard-order-btn", () => discardQueueManualOrderDraft());', queue_view_js)
        self.assertIn('row.addEventListener("drop"', queue_view_js)
        self.assertIn('event.key !== "ArrowUp" && event.key !== "ArrowDown"', queue_view_js)
        self.assertIn('ManualOrder takes effect on the next backend queue build.', queue_view_js)
        self.assertIn("wireManualOrderRow", queue_table_js)
        self.assertIn("dataset.manualOrderDraggable", queue_table_js)
        self.assertIn(".queue-manual-order-toolbar", queue_css)
        self.assertIn(".is-manual-drop-target", queue_css)
        self.assertIn('.priority-badge[data-level="high"]', queue_css)
        self.assertIn('background: var(--semantic-info-bg);', queue_css)
        self.assertIn("#queue-filter-summary {\n  display: none !important;\n}", queue_css)
        self.assertIn('[data-page-panel="queue"] .queue-table tr.is-selected[data-status="warning"] td:first-child', queue_css)
        self.assertIn('[data-page-panel="queue"] .queue-table tr.is-selected[data-status="blocked"] td:first-child', queue_css)

    def test_queue_file_settings_drawer_stage2_annotations_and_focus(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        queue_table_js = (assets_root / "queue" / "table.js").read_text(encoding="utf-8")
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_css = _read_queue_css(assets_root)

        self.assertIn('openFileSettingsDrawer(item, { trigger: button });', queue_table_js)
        self.assertIn('button.textContent = "File overrides";', queue_table_js)
        self.assertNotIn('button.textContent = "⚙";', queue_table_js)
        self.assertIn('aria-describedby="fo-drawer-scope-summary fo-inherited-settings-status fo-drawer-status"', html)
        self.assertIn('tabindex="-1"', html)
        self.assertIn('id="fo-inherited-settings-status"', html)
        self.assertIn('id="fo-drawer-title" class="fo-drawer-title">File overrides</h3>', html)
        self.assertIn('id="fo-drawer-scope-summary"', html)
        self.assertIn('class="fo-drawer-footer" aria-label="File override actions"', html)
        self.assertIn('id="fo-drawer-save" class="primary-button" disabled', html)
        self.assertIn('id="fo-drawer-status" class="fo-drawer-status" role="status" aria-live="polite" data-tone="info"', html)
        for field_key, hint_id in [
            ("audioKeepLanguages", "fo-audio-keep-langs-inherited"),
            ("audioDropLanguages", "fo-audio-drop-langs-inherited"),
            ("audioMaxChannels", "fo-audio-max-channels-inherited"),
            ("subtitleKeepLanguages", "fo-sub-keep-langs-inherited"),
            ("subtitleDropLanguages", "fo-sub-drop-langs-inherited"),
            ("subtitleStripAll", "fo-sub-strip-all-inherited"),
        ]:
            self.assertIn(f'data-fo-field="{field_key}"', html)
            self.assertIn(f'id="{hint_id}" class="fo-inherited-hint"', html)
        self.assertGreaterEqual(html.count('data-fo-overridden-badge hidden>Overridden</span>'), 6)

        self.assertIn("function getDrawerLibraryDefaults(item)", queue_view_js)
        self.assertIn('settingKey: "PreferredDefaultAudioLanguages"', queue_view_js)
        self.assertIn('settingKey: "AudioMaxChannels"', queue_view_js)
        self.assertIn('settingKey: "SubKeepLanguages"', queue_view_js)
        self.assertIn("item?.library_effective_settings", queue_view_js)
        self.assertIn("item?.library_settings_overrides", queue_view_js)
        self.assertIn("item?.has_file_override", queue_table_js)
        self.assertIn('"File — " + (name.length > 40 ? name.slice(0, 40) + "…" : name)', queue_view_js)
        self.assertNotIn('"File Settings — " + (name.length > 40 ? "…" + name.slice(-40) : name)', queue_view_js)
        self.assertIn("/api/queue/file-overrides/effective", queue_view_js)
        self.assertIn("const FILE_OVERRIDES_EFFECTIVE_ROUTE", queue_view_js)
        self.assertIn("function loadFileOverrideEffectiveForPath(path, item, token", queue_view_js)
        self.assertIn("function applyFileOverrideEffectivePayload(payload, item)", queue_view_js)
        self.assertIn("function drawerDefaultsFromEffectivePayload(payload, item)", queue_view_js)
        self.assertIn("await loadFileOverrideEffectiveForPath(state.foCurrentPath, state.foCurrentItem);", queue_view_js)
        self.assertIn("function renderDrawerInheritedDefaults(defaults)", queue_view_js)
        self.assertIn('Saved policy values unavailable for this queue row.', queue_view_js)
        self.assertIn("Saved policy value: unavailable", queue_view_js)
        self.assertIn("function renderDrawerOverrideMarkers(entry)", queue_view_js)
        self.assertIn('setDrawerFieldOverridden(fieldKey, state[fieldKey])', queue_view_js)
        self.assertIn('subtitleBurnTrack: isPlainObject(subs.burnTrack)', queue_view_js)
        self.assertIn('subtitleStripAll: hasOwnValue(subs, "stripAll")', queue_view_js)
        self.assertIn("clearDrawerOverrideMarkers();", queue_view_js)
        self.assertIn("function restoreFileSettingsDrawerFocus()", queue_view_js)
        self.assertIn("trigger.isConnected", queue_view_js)
        self.assertIn("trigger.focus();", queue_view_js)
        self.assertIn("function handleFileSettingsDrawerKeydown(event)", queue_view_js)
        self.assertIn('if (event.key === "Escape")', queue_view_js)
        self.assertIn("requestCloseFileSettingsDrawer();", queue_view_js)
        self.assertIn('if (event.key !== "Tab") return;', queue_view_js)
        self.assertIn("event.shiftKey && active === first", queue_view_js)
        self.assertIn("!event.shiftKey && active === last", queue_view_js)
        self.assertIn("document.addEventListener(\"keydown\", ctx.focus.handleFileSettingsDrawerKeydown);", queue_view_js)

        self.assertIn(".fo-inherited-hint", queue_css)
        self.assertIn(".fo-inherited-status", queue_css)
        self.assertIn(".fo-drawer-footer", queue_css)
        self.assertIn('.fo-drawer-status[data-tone="error"]', queue_css)
        self.assertIn('.fo-drawer-status[data-tone="success"]', queue_css)
        self.assertIn('.fo-field[data-overridden="true"]', queue_css)
        self.assertIn(".fo-overridden-badge", queue_css)

    def test_queue_file_settings_drawer_use_inherited_controls(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_css = _read_queue_css(assets_root)

        field_paths = {
            "audioKeepLanguages": "audio.keepTracks",
            "audioDropLanguages": "audio.dropTracks",
            "audioMaxChannels": "audio.maxChannels",
            "audioPreferDefaultLanguage": "audio.preferDefaultLanguage",
            "subtitleKeepLanguages": "subtitles.keepTracks",
            "subtitleDropLanguages": "subtitles.dropTracks",
            "subtitleStripAll": "subtitles.stripAll",
        }
        aria_labels = {
            "audioKeepLanguages": "Use saved policy value for audio keep languages",
            "audioDropLanguages": "Use saved policy value for audio drop languages",
            "audioMaxChannels": "Use saved policy value for audio max channels",
            "audioPreferDefaultLanguage": "Use saved policy value for preferred default audio language",
            "subtitleKeepLanguages": "Use saved policy value for subtitle keep languages",
            "subtitleDropLanguages": "Use saved policy value for subtitle drop languages",
            "subtitleStripAll": "Use saved policy value for subtitle strip all",
        }
        for field_key, field_path in field_paths.items():
            self.assertRegex(
                html,
                rf'<button type="button" class="fo-use-inherited-button" data-fo-use-inherited="{field_key}" '
                rf'aria-label="{aria_labels[field_key]}" hidden>Use saved policy</button>',
            )
            self.assertIn(f'{field_key}: "{field_path}"', queue_view_js)
        self.assertIn('subtitleBurnTrack: "subtitles.burnTrack"', queue_view_js)

        self.assertIn("function clearFileOverrideField(fieldKey)", queue_view_js)
        self.assertIn("clear_fields: [fieldPath]", queue_view_js)
        self.assertIn("function stageUseSavedPolicyField(fieldKey)", queue_view_js)
        self.assertIn("state.foPendingClearFieldPaths.add(fieldPath);", queue_view_js)
        self.assertIn('setStatus("Saved policy staged locally. Use Save Override to persist this field clear, or close to discard.", "warning");', queue_view_js)
        self.assertIn('button.textContent = staged ? "Saved policy staged" : text;', queue_view_js)
        self.assertIn('button.dataset.stagedClear = "true";', queue_view_js)
        self.assertIn('button.addEventListener("click", () => ctx.form.stageUseSavedPolicyField(button.dataset.foUseInherited || ""));', queue_view_js)
        self.assertIn("foPendingClearFieldPaths: new Set(),", queue_view_js)
        self.assertIn("foDrawerLoading: false,", queue_view_js)
        self.assertIn("function drawerRequestIsCurrent(path, token = state.foDrawerLoadToken)", queue_view_js)
        self.assertIn("if (!drawerRequestIsCurrent(path, token)) return false;", queue_view_js)
        self.assertIn('payload.file_override_scope !== "file"', queue_view_js)
        self.assertIn('sources[fieldPath] === "file_override"', queue_view_js)
        self.assertIn("function renderDrawerUseInheritedButtons(payload)", queue_view_js)
        self.assertIn("setDrawerUseInheritedAvailable(fieldKey, Boolean(state[fieldKey] && isExactFileOverride));", queue_view_js)
        self.assertIn("function savedPolicyButtonText(fieldKey)", queue_view_js)
        self.assertIn("function savedPolicyOptionText(fieldKey)", queue_view_js)
        self.assertIn('document.querySelectorAll("[data-fo-use-inherited]")', queue_view_js)
        self.assertIn("foCommandInFlight: false,", queue_view_js)
        self.assertIn("foDrawerBaselineSignature: \"\",", queue_view_js)
        self.assertIn("foDrawerDirty: false,", queue_view_js)
        self.assertIn("function setDrawerCommandButtonsDisabled(disabled)", queue_view_js)
        self.assertIn("function markDrawerClean()", queue_view_js)
        self.assertIn("function handleDrawerFormChanged()", queue_view_js)
        self.assertIn("function confirmDiscardDrawerChanges", queue_view_js)
        self.assertIn('if (state.foCommandInFlight) { setStatus("File override command already in progress."); return; }', queue_view_js)
        self.assertIn("state.foCommandInFlight = true;", queue_view_js)
        self.assertIn("setDrawerCommandButtonsDisabled(true);", queue_view_js)
        self.assertIn("setDrawerCommandButtonsDisabled(false);", queue_view_js)
        self.assertIn('if (!state.foDrawerDirty) { setStatus("No unsaved changes to save.", "warning"); return; }', queue_view_js)
        self.assertIn("await loadFileOverrideEffectiveForPath(state.foCurrentPath, state.foCurrentItem);", queue_view_js)
        self.assertIn("Override field cleared. Saved policy value will be used.", queue_view_js)
        self.assertIn("await refreshAllFn();", queue_view_js)
        self.assertIn("function saveFileOverrideForPath()", queue_view_js)
        self.assertIn("function clearFileOverrideForPath()", queue_view_js)
        self.assertIn("function handleFileSettingsDrawerKeydown(event)", queue_view_js)
        self.assertIn('if (event.key === "Escape")', queue_view_js)
        self.assertIn("Discard unsaved file override changes", queue_view_js)
        self.assertIn("function restoreFileSettingsDrawerFocus()", queue_view_js)
        self.assertIn(".fo-use-inherited-button", queue_css)
        self.assertIn('.fo-use-inherited-button[data-staged-clear="true"]', queue_css)
        self.assertIn(".fo-use-inherited-button:disabled", queue_css)

    def test_queue_file_settings_drawer_stage4f_audio_preferred_default_language(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)

        self.assertIn('data-fo-field="audioPreferDefaultLanguage"', html)
        self.assertIn('for="fo-audio-prefer-default-language">Preferred default language</label>', html)
        self.assertIn(
            'data-fo-use-inherited="audioPreferDefaultLanguage" aria-label="Use saved policy value for preferred default audio language" hidden>Use saved policy</button>',
            html,
        )
        self.assertIn(
            'id="fo-audio-prefer-default-language" class="fo-input" placeholder="e.g. eng — blank = use saved policy" aria-describedby="fo-audio-prefer-default-language-inherited"',
            html,
        )
        self.assertIn('id="fo-audio-prefer-default-language-inherited" class="fo-inherited-hint"', html)

        self.assertIn('audioPreferDefaultLanguage: "fo-audio-prefer-default-language-inherited"', queue_view_js)
        self.assertIn('audioPreferDefaultLanguage: "audio.preferDefaultLanguage"', queue_view_js)
        self.assertIn('scalarLanguage: true', queue_view_js)
        self.assertIn('payload?.expanded_effective_fields', queue_view_js)
        self.assertIn('preferDefaultLanguage.value = String(audio.preferDefaultLanguage || "").trim();', queue_view_js)
        self.assertIn('audioPreferDefaultLanguage: hasOwnValue(audio, "preferDefaultLanguage")', queue_view_js)
        self.assertIn('if (preferDefaultLanguage) audio.preferDefaultLanguage = preferDefaultLanguage;', queue_view_js)
        self.assertIn('function backendErrorMessage(result, fallback = "Unknown error.")', queue_view_js)

    def test_queue_file_settings_drawer_stage5e_route_controls(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_css = _read_queue_css(assets_root)

        self.assertIn('id="fo-processing-route-section" class="fo-section fo-route-section" hidden', html)
        self.assertIn("These settings can change whether this file is remuxed or fully transcoded.", html)
        self.assertIn('id="fo-route-preview-status" class="fo-route-preview-status" aria-live="polite" hidden', html)
        self.assertIn('id="fo-route-encode-advisory" class="fo-route-encode-advisory" aria-live="polite" data-tone="info" hidden', html)
        self.assertNotIn('id="fo-route-risk-confirmation"', html)
        self.assertNotIn('id="fo-route-risk-confirm"', html)
        self.assertNotIn("I understand this may force a full transcode for this file.", html)

        route_fields = {
            "routeProfile": ("fo-route-profile", "routing.profile", "Use saved policy value for routing profile"),
            "routingRouteThresholdMode": ("fo-route-threshold-mode", "routing.routeThresholdMode", "Use saved policy value for route threshold mode"),
            "videoCodec": ("fo-video-codec", "video.codec", "Use saved policy value for video codec"),
            "videoContainer": ("fo-video-container", "video.container", "Use saved policy value for output container"),
            "videoEncodePreset": ("fo-video-encode-preset", "video.encodePreset", "Use saved policy value for encode preset"),
            "videoEncodeLadder": ("fo-video-encode-ladder", "video.encodeLadder", "Use saved policy value for encode ladder"),
        }
        for field_key, (control_id, field_path, aria_label) in route_fields.items():
            self.assertIn(f'data-fo-field="{field_key}" hidden', html)
            self.assertIn(f'id="{control_id}" class="fo-select" data-fo-route-control="{field_key}"', html)
            self.assertIn('<option value="">Use saved policy</option>', html)
            self.assertIn(
                f'data-fo-use-inherited="{field_key}" aria-label="{aria_label}" hidden>Use saved policy</button>',
                html,
            )
            self.assertIn(f'{field_key}: "{field_path}"', queue_view_js)

        self.assertIn('apiPost("/api/queue/file-overrides/route-preview", {', queue_view_js)
        self.assertIn("function renderProcessingRouteControls(payload)", queue_view_js)
        self.assertIn("payload?.route_video_effective_fields", queue_view_js)
        self.assertIn("safeNormalizeRouteChoiceOptions(metadata)", queue_view_js)
        self.assertIn("safePopulateRouteSelectOptions(control, choices)", queue_view_js)
        self.assertIn("function routePreviewProposalFromPayload(payload)", queue_view_js)
        self.assertIn("proposed.subtitles = { burnTrack: payload.subtitles.burnTrack };", queue_view_js)
        self.assertIn("forceRoute = profile", queue_view_js)
        self.assertIn("routingProfile = profile", queue_view_js)
        self.assertIn("function ensureRoutePreviewAllowsSave(payload)", queue_view_js)
        self.assertIn("await loadRoutePreviewForPayload(payload)", queue_view_js)
        self.assertIn("function routePreviewEncodeAdvisory(result)", queue_view_js)
        self.assertIn("Force encode: backend preview says these settings can route this file to a full video encode/transcode.", queue_view_js)
        self.assertIn("May encode: possible. These settings can change remux-vs-encode routing; backend preview did not prove a forced encode.", queue_view_js)
        self.assertIn("Will Remux: backend preview keeps this file on remux/copy; review any route warnings before saving.", queue_view_js)
        self.assertNotIn("May encode: no.", queue_view_js)
        self.assertNotIn("Confirm the route impact before saving this processing override.", queue_view_js)
        self.assertNotIn("fo-route-risk-confirm", queue_view_js)
        self.assertIn("function collectFileOverrideFieldsToClearOnSave()", queue_view_js)
        self.assertIn("function collectRouteVideoFieldsToClearOnSave()", queue_view_js)
        self.assertIn("function drawerFieldIsNeutral(fieldKey)", queue_view_js)
        self.assertIn('sources[fieldPath] === "file_override"', queue_view_js)
        self.assertIn("&& drawerFieldIsNeutral(fieldKey)", queue_view_js)
        self.assertIn("const clearFields = collectFileOverrideFieldsToClearOnSave();", queue_view_js)
        self.assertIn("clear_fields: clearFields", queue_view_js)
        self.assertIn("function fieldPathsIncludeRouteVideo(fieldPaths)", queue_view_js)
        self.assertIn("clear_fields: [fieldPath]", queue_view_js)
        self.assertIn("ROUTE_FIELD_KEYS.includes(fieldKey)", queue_view_js)
        self.assertIn('control.addEventListener("change", ctx.routePreview.scheduleRoutePreviewFromCurrentForm);', queue_view_js)
        self.assertIn(".fo-route-preview-status", queue_css)
        self.assertIn(".fo-route-encode-advisory", queue_css)
        self.assertNotIn(".fo-route-confirmation", queue_css)

    def test_queue_file_settings_drawer_series_batch_preview_modal(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_css = _read_queue_css(assets_root)

        self.assertIn('id="fo-series-preview-open"', html)
        self.assertIn('id="fo-series-auto-detect" checked', html)
        self.assertIn('id="fo-series-modal" class="fo-series-modal" role="dialog"', html)
        self.assertIn('data-fo-series-filter="will_update"', html)
        self.assertIn('data-fo-series-filter="protected"', html)
        self.assertIn('data-fo-series-filter="issues"', html)
        self.assertIn('id="fo-series-apply" class="primary-button" disabled', html)
        self.assertIn('id="fo-remux-pilot-promote" class="secondary-button" hidden', html)
        self.assertIn('id="fo-remux-pilot-proof" class="fo-remux-pilot-proof"', html)

        self.assertIn('apiPost("/api/queue/file-overrides/series-preview", {', queue_view_js)
        self.assertIn('apiPost("/api/queue/file-overrides/series-apply", {', queue_view_js)
        self.assertIn('apiPost("/api/queue/file-overrides/remux-pilot-promote", {', queue_view_js)
        self.assertIn("function requestSeriesPreview()", queue_view_js)
        self.assertIn("function applySeriesPreview()", queue_view_js)
        self.assertIn("function requestRemuxPilotPromotion()", queue_view_js)
        self.assertIn("function selectedPilotSourcePaths()", queue_view_js)
        self.assertIn("pilot_source_paths: pilotPaths", queue_view_js)
        self.assertIn("function renderSeriesPreview(payload)", queue_view_js)
        self.assertIn("function renderRemuxPilotPromotionResult(result)", queue_view_js)
        self.assertIn("function hideDrawerForSeriesModal()", queue_view_js)
        self.assertIn("function restoreDrawerAfterSeriesModal()", queue_view_js)
        self.assertIn("hideDrawerForSeriesModal();", queue_view_js)
        self.assertIn("closeSeriesModal({ restoreFocus: false, restoreDrawer: false });", queue_view_js)
        self.assertIn("closeFileSettingsDrawer();", queue_view_js)
        self.assertIn("preview_fingerprint: fingerprint", queue_view_js)
        self.assertIn("confirm_apply: true", queue_view_js)
        self.assertIn("window.getSelectedQueuePriorityRows = getSelectedQueuePriorityRows;", queue_view_js)
        self.assertIn('remuxPilotBtn.addEventListener("click", ctx.series.requestRemuxPilotPromotion);', queue_view_js)
        self.assertIn('button.addEventListener("click", () => {', queue_view_js)
        self.assertIn("ctx.series.renderSeriesRows(ctx.state.foSeriesPreviewPayload?.rows);", queue_view_js)
        self.assertIn("closeSeriesModal()", queue_view_js)

        self.assertIn(".fo-series-modal", queue_css)
        self.assertIn(".fo-series-table", queue_css)
        self.assertIn(".fo-series-filters", queue_css)
        self.assertIn(".fo-remux-pilot-proof", queue_css)

    def test_queue_file_settings_drawer_stage6e_track_metadata_sections(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_css = _read_queue_css(assets_root)

        self.assertIn('id="fo-source-info-section" class="fo-section fo-source-info-section"', html)
        self.assertIn("Detected file info", html)
        self.assertIn('id="fo-source-info-grid" class="fo-source-info-grid"', html)
        self.assertIn('id="fo-source-info-status" class="fo-source-info-status" aria-live="polite"', html)
        self.assertIn('id="fo-source-info-missing" class="fo-source-info-missing" aria-live="polite"', html)
        self.assertIn('id="fo-track-metadata-section" class="fo-section fo-track-section"', html)
        self.assertIn("Detected audio tracks", html)
        self.assertIn("Detected subtitle tracks", html)
        self.assertIn("Detected track details remain visible; use track actions for file-level exact overrides or language fields as fallback.", html)
        self.assertIn('id="fo-audio-track-list" class="fo-track-list"', html)
        self.assertIn('id="fo-subtitle-track-list" class="fo-track-list"', html)
        self.assertIn('id="fo-track-warning-list" class="fo-track-warning-list" aria-live="polite"', html)
        self.assertNotIn("data-fo-track-action", html)

        self.assertIn("function renderDrawerTrackMetadata(payload)", queue_view_js)
        self.assertIn('const FILE_OVERRIDES_TRACKS_ROUTE = "/api/queue/file-overrides/tracks";', queue_view_js)
        self.assertIn("function loadFileOverrideTracksForPath(path, token", queue_view_js)
        self.assertIn("function trackMetadataFromTracksPayload(payload)", queue_view_js)
        self.assertIn("payload?.track_metadata", queue_view_js)
        self.assertIn("payload?.track_selection_preview", queue_view_js)
        self.assertIn("payload?.resolved_track_actions", queue_view_js)
        self.assertIn("function renderDrawerSourceInfo(sourceInfo)", queue_view_js)
        self.assertIn("source_info: isPlainObject(payload?.source_info)", queue_view_js)
        self.assertIn("sourceInfoEstimatedBitrateText(info)", queue_view_js)
        self.assertIn("fo-source-info-status", queue_view_js)
        self.assertIn('appendTrackDetail(details, "Bitrate", track.bitrate_display);', queue_view_js)
        self.assertIn("function createTrackRow(track, kind, preview, resolvedActions)", queue_view_js)
        self.assertIn("function resolvedActionsByStream(section)", queue_view_js)
        self.assertIn("function resolvedActionForTrack(resolvedActions, track)", queue_view_js)
        self.assertIn("Source default track", queue_view_js)
        self.assertNotIn("Kept by default", queue_view_js)
        self.assertIn("kept_stream_indexes", queue_view_js)
        self.assertIn("dropped_stream_indexes", queue_view_js)
        self.assertIn("burned_stream_indexes", queue_view_js)
        self.assertIn("kept_stream_sources", queue_view_js)
        self.assertIn("dropped_stream_sources", queue_view_js)
        self.assertIn("burned_stream_sources", queue_view_js)
        self.assertIn("renderDrawerTrackMetadata(payload);", queue_view_js)
        self.assertIn("clearDrawerTrackMetadata();", queue_view_js)
        self.assertIn("resetTrackMetadata: false", queue_view_js)
        self.assertIn("appears to be commentary", queue_view_js)
        self.assertIn("is marked forced", queue_view_js)
        self.assertIn("image-based and may require OCR or burn-in review", queue_view_js)

        self.assertIn(".fo-source-info-section", queue_css)
        self.assertIn(".fo-source-info-grid", queue_css)
        self.assertIn(".fo-source-info-fact", queue_css)
        self.assertIn(".fo-source-info-missing", queue_css)
        self.assertIn(".fo-track-section", queue_css)
        self.assertIn(".fo-track-list", queue_css)
        self.assertIn(".fo-track-row", queue_css)
        self.assertIn(".fo-track-badge", queue_css)
        self.assertIn(".fo-track-warning-list", queue_css)

    def test_queue_file_settings_drawer_stage6h_exact_track_controls(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        assets_root = static_root / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_css = _read_queue_css(assets_root)

        self.assertIn("function createTrackActionControl(track, kind, resolvedAction)", queue_view_js)
        self.assertIn('select.dataset.foTrackAction = "true";', queue_view_js)
        self.assertIn('select.dataset.foTrackKind = kind;', queue_view_js)
        self.assertIn('select.dataset.foTrackIndexAvailable = streamIndex === null ? "false" : "true";', queue_view_js)
        self.assertIn('select.dataset.foTrackJson = JSON.stringify(track);', queue_view_js)
        self.assertIn('["", trackPipelineOptionText(resolvedAction)]', queue_view_js)
        self.assertIn("Use pipeline policy: resolved", queue_view_js)
        self.assertIn('["keep", kind === "audio" ? "Keep this audio track" : "Keep this subtitle track"]', queue_view_js)
        self.assertIn('["drop", kind === "audio" ? "Drop this audio track" : "Drop this subtitle track"]', queue_view_js)
        self.assertIn('options.push(["burn", "Burn into video"]);', queue_view_js)
        self.assertIn('select.setAttribute("aria-label", `Override action for ${kind === "audio" ? "audio" : "subtitle"} stream ${streamIndex ?? "unknown"}`);', queue_view_js)
        self.assertIn("function exactSelectorForTrack(track, kind)", queue_view_js)
        self.assertIn("const selector = { streamIndex };", queue_view_js)
        self.assertIn("selector.language = language;", queue_view_js)
        self.assertIn("selector.codec = codec;", queue_view_js)
        self.assertIn("selector.channels = channels;", queue_view_js)
        self.assertIn("selector.forced = Boolean(track.forced);", queue_view_js)
        self.assertIn("function collectExactTrackSelectorsFromControls()", queue_view_js)
        self.assertIn("function currentFileOverridePathLooksFileLike()", queue_view_js)
        self.assertIn("Exact stream selectors can only be saved for a file path, not a folder or library scope.", queue_view_js)
        self.assertIn('appendSelectorRules(audio, "keepTracks", exactTrackSelectors.audioKeep);', queue_view_js)
        self.assertIn('appendSelectorRules(audio, "dropTracks", exactTrackSelectors.audioDrop);', queue_view_js)
        self.assertIn('appendSelectorRules(subtitles, "keepTracks", exactTrackSelectors.subtitleKeep);', queue_view_js)
        self.assertIn('appendSelectorRules(subtitles, "dropTracks", exactTrackSelectors.subtitleDrop);', queue_view_js)
        self.assertIn("subtitles.burnTrack = exactTrackSelectors.subtitleBurn[0];", queue_view_js)
        self.assertIn("state.foExactTrackOverrideEntry = payload.file_override_scope === \"file\"", queue_view_js)
        self.assertIn("Saved exact-track override no longer matches detected track metadata", queue_view_js)
        self.assertIn("Saved exact-track override cannot be safely resaved.", queue_view_js)
        self.assertIn("Choose only one subtitle stream to burn into the video.", queue_view_js)
        self.assertIn("function confirmSubtitleBurnBeforeSave(payload)", queue_view_js)
        self.assertIn("Drops selectable subtitles", queue_view_js)
        self.assertIn("Destructive output change", queue_view_js)
        self.assertIn("function resetExactTrackActionsForField(fieldKey)", queue_view_js)
        self.assertIn("resetExactTrackActionsForField(fieldKey);", queue_view_js)
        self.assertIn('document.querySelectorAll(\'[data-fo-track-action][data-fo-track-kind="subtitle"]\')', queue_view_js)
        self.assertIn("function validateExactTrackSelectionsBeforeSave()", queue_view_js)
        self.assertIn("if (payload && !validateExactTrackSelectionsBeforeSave()) return;", queue_view_js)

        self.assertIn(".fo-track-action", queue_css)
        self.assertIn(".fo-track-action-select", queue_css)

    def test_queue_file_settings_drawer_does_not_render_folder_rule_ui(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        queue_view_js = _read_queue_file_overrides_asset_bundle(assets_root)
        queue_css = _read_queue_css(assets_root)
        index_html = (static_root / "index.html").read_text(encoding="utf-8")

        removed_markup = [
            "fo-folder-preview-open",
            "fo-folder-preview-panel",
            "fo-folder-preview-scope-select",
            "fo-folder-preview-save",
            "fo-folder-rules-open",
            "fo-folder-rules-panel",
            "Folder rule impact",
            "Existing folder rules",
        ]
        for text in removed_markup:
            self.assertNotIn(text, html)
        self.assertNotIn("fileOverrides.folderPreview.js", index_html)

        removed_js = [
            "createFileOverridesFolderPreviewModule",
            "__queueFileOverridesFolderPreviewModule",
            "openFolderRulePreviewPanel",
            "loadFolderRulesForDrawer",
            "fo-folder-preview",
            "fo-folder-rules",
            "/api/queue/file-overrides/folder-preview",
            "/api/queue/file-overrides/folder-rule",
        ]
        for text in removed_js:
            self.assertNotIn(text, queue_view_js)

        removed_css = [
            ".fo-folder-preview",
            ".fo-folder-rules",
            ".fo-folder-rule",
            ".fo-inline-link",
        ]
        for text in removed_css:
            self.assertNotIn(text, queue_css)

    def test_diagnostics_ui_hardening_affordances_are_static_pinned(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        dom_helpers_js = _read_dom_helpers_asset_bundle(assets_root)
        table_js = (assets_root / "dom" / "table.js").read_text(encoding="utf-8")
        diagnostics_view_js = _read_diagnostics_asset_bundle(assets_root)
        diagnostics_tail_js = (assets_root / "diagnosticsTailView.js").read_text(encoding="utf-8")
        diagnostics_state_js = (assets_root / "diagnosticsStateSummaryView.js").read_text(encoding="utf-8")
        diagnostics_bridge_js = (assets_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        command_history_js = _read_command_history_asset_bundle(assets_root)
        contract_view_js = (assets_root / "contractView.js").read_text(encoding="utf-8")
        app_js = "\n".join(
            (assets_root / name).read_text(encoding="utf-8")
            for name in ("app.js", "app/refreshCoordinator.js")
        )
        diagnostics_html = (static_root / "partials" / "page-diagnostics.html").read_text(encoding="utf-8")
        styles_css = resolved_css_asset_bundle(assets_root)

        for symbol in [
            "function setPanelStatus",
            "function setInlineActionStatus",
            "function setActionBusy",
            "normalizePanelStatusState",
            "window.setPanelStatus = setPanelStatus",
        ]:
            self.assertIn(symbol, dom_helpers_js)

        for tbody_id in [
            "diagnostics-first-response-rows",
            "diagnostics-state-triage-rows",
            "diagnostics-state-summary-rows",
            "diagnostics-owner-handoff-rows",
            "diagnostics-command-drilldown-rows",
            "diagnostics-command-evidence-rows",
            "diagnostics-command-resolution-rows",
            "api-contract-safety-rows",
            "tdarr-matrix-proof-pack-rows",
        ]:
            self.assertIn(f'"{tbody_id}"', table_js)

        self.assertIn('id="diagnostics-pipeline-log-status"', html)
        self.assertIn('id="diagnostics-launch-log-status"', html)
        self.assertIn('id="tdarr-matrix-delete-confirm"', html)
        self.assertIn('data-severity="warning" data-tdarr-matrix-audit-action="cleanup-plan"', html)
        self.assertIn('data-read-diagnostics-tail="last_stderr_log"', html)
        self.assertIn('data-read-diagnostics-tail="queue_snapshot"', html)
        self.assertIn('diagnostics-open-target-groups', html)
        self.assertLess(diagnostics_html.index("<h2>Command Detail</h2>"), diagnostics_html.index("<h2>Commands Evidence</h2>"))

        self.assertIn("function tdarrMatrixActionGate", diagnostics_view_js)
        self.assertIn("Type DELETE VERIFIED MATRIX", diagnostics_view_js)
        self.assertIn("confirm_delete_full_matrix = true", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsRefreshFailures", diagnostics_view_js)
        self.assertIn("function diagnosticsLogPanelStatus", diagnostics_view_js)
        self.assertIn('"log_tail_missing"', diagnostics_view_js)
        self.assertIn('"launch_logs_error"', diagnostics_view_js)
        self.assertIn("if (resultOk) {", diagnostics_view_js)
        self.assertIn("renderDiagnosticsRefreshFailuresFn(failures)", app_js)
        self.assertIn("requestDiagnosticsOpen(openTarget, button)", diagnostics_view_js)
        self.assertIn("requestDiagnosticsTail(artifact.tailTarget, tailButton)", diagnostics_view_js)
        self.assertIn("setInlineActionStatus(sourceButton", diagnostics_tail_js)
        self.assertIn('"Read error"', diagnostics_tail_js)
        self.assertIn('"Missing"', diagnostics_tail_js)
        self.assertIn('"Empty"', diagnostics_tail_js)
        self.assertIn("requestDiagnosticsTail(target, button)", diagnostics_state_js)
        self.assertIn("onAction(action, button)", diagnostics_bridge_js)
        self.assertIn("requestCommandDiagnosticsAction(action, button)", command_history_js)
        self.assertIn("Operator boundary: route presence is evidence only", contract_view_js)
        self.assertIn("Diagnostics handoff selected this row locally. No backend command was sent.", diagnostics_view_js)
        self.assertIn(".inline-action-status[data-state=\"blocked\"]", styles_css)
        self.assertIn(".secondary-button[data-severity=\"warning\"]", styles_css)

    def test_web_selected_rows_share_diagnostics_handoff(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        diagnostics_bridge_js = (assets_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        queue_view_js = _read_queue_asset_bundle(assets_root)
        completed_view_js = _read_completed_asset_bundle(assets_root)
        pending_view_js = _read_pending_publish_asset_bundle(assets_root)
        reports_shell_js = (assets_root / "reports" / "shell.js").read_text(encoding="utf-8")
        reports_audit_model_js = (assets_root / "reports" / "auditModel.js").read_text(encoding="utf-8")
        reports_audit_view_js = (assets_root / "reports" / "auditView.js").read_text(encoding="utf-8")
        reports_failure_model_js = (assets_root / "reports" / "failureModel.js").read_text(encoding="utf-8")
        reports_failure_view_js = (assets_root / "reports" / "failureView.js").read_text(encoding="utf-8")
        command_history_js = _read_command_history_asset_bundle(assets_root)
        diagnostics_view_js = _read_diagnostics_asset_bundle(assets_root)
        diagnostics_view_investigation_js = (assets_root / "diagnosticsView.investigation.js").read_text(encoding="utf-8")

        for node_id in [
            "command-diagnostics-actions",
            "failure-diagnostics-actions",
            "audit-preview-diagnostics-actions",
        ]:
            self.assertIn(f'id="{node_id}"', html)

        self.assertIn("function diagnosticsBridgeHandoffLines", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeTargetLabel", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeOrderedActions", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeActionGroups", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeRowTrustLines", diagnostics_bridge_js)
        self.assertIn("function appendDiagnosticsBridgeGroupedButtons", diagnostics_bridge_js)
        self.assertIn("Operator trust summary:", diagnostics_bridge_js)
        self.assertIn("Read first:", diagnostics_bridge_js)
        self.assertIn("Open next:", diagnostics_bridge_js)
        self.assertIn("renderOpenTargetActionGroups?.(container, groups", diagnostics_bridge_js)
        self.assertIn('groupDataset: "diagnosticsActionGroup"', diagnostics_bridge_js)
        self.assertIn("targetDataset: `${datasetPrefix}Target`", diagnostics_bridge_js)
        self.assertIn("Guardrail: this handoff selects or invokes backend allowlisted diagnostics targets only", diagnostics_bridge_js)
        _assert_namespace_export(self, diagnostics_bridge_js, "mediaPipelineDiagnosticsBridge", "diagnosticsBridgeHandoffLines")
        self.assertNotIn("window.diagnosticsBridgeHandoffLines = diagnosticsBridgeHandoffLines", diagnostics_bridge_js)

        self.assertIn('diagnosticsBridgeHandoffLines("Queue selected row"', queue_view_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Completed selected row"', completed_view_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Pending Publish selected row"', pending_view_js)

        self.assertIn("function failureDiagnosticsActionsForRow", reports_failure_model_js)
        self.assertIn("function auditDiagnosticsActionsForRow", reports_audit_model_js)
        self.assertIn("function renderReportDiagnosticsActions", reports_shell_js)
        self.assertIn('renderReportDiagnosticsActions("failure-diagnostics-actions", failureDiagnosticsActionsForGroup(current), "Reports failure selected group")', reports_failure_view_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Reports audit selected row"', reports_audit_view_js)
        self.assertIn("button.dataset.reportDiagnosticsTarget = action.target", reports_shell_js)
        self.assertIn("bridge.appendDiagnosticsBridgeButton(container, actions, sourceLabel)", reports_shell_js)

        self.assertIn("function commandHistoryDiagnosticsActions", command_history_js)
        self.assertIn("commandHistoryDiagnosticsActions,", command_history_js)
        self.assertIn("commandHistoryIssueEntries,", command_history_js)
        self.assertIn("commandHistoryView.commandHistoryIssueEntries(entries)", diagnostics_view_investigation_js)
        self.assertNotIn("window.commandHistoryIssueEntries = commandHistoryIssueEntries", command_history_js)
        self.assertNotIn("window.commandHistoryDiagnosticsActions = commandHistoryDiagnosticsActions", command_history_js)
        self.assertIn("function commandHistoryDiagnosticsTargetAllowed", command_history_js)
        self.assertIn("commandHistoryDiagnosticsTargetAllowed(requestedTarget)", command_history_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Command result selected row"', command_history_js)
        self.assertIn('byId("command-diagnostics-actions")', command_history_js)
        self.assertIn("button.dataset.commandDiagnosticsTarget = action.target", command_history_js)
        self.assertIn("commandHistoryView.commandHistorySuggestedAction(entry)", diagnostics_view_js)

    def test_diagnostics_bridge_namespace_exports_cover_helper_consumers(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        assets_root = desktop_root / "apps" / "desktop" / "webview" / "static" / "assets"
        diagnostics_bridge_js = (assets_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        helper_names = {
            "diagnosticsBridgeActions",
            "diagnosticsBridgeActionLabel",
            "diagnosticsBridgeOrderedActions",
            "diagnosticsBridgeRowTrustLines",
            "diagnosticsBridgeHandoffLines",
            "appendDiagnosticsBridgeGroupedButtons",
            "appendDiagnosticsBridgeButton",
        }
        consumer_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(assets_root.glob("*.js"))
            if path.name != "diagnosticsBridge.js"
        )
        consumed_helpers = sorted(
            name
            for name in helper_names
            if re.search(rf"(?<![A-Za-z0-9_$]){re.escape(name)}(?![A-Za-z0-9_$])", consumer_text)
        )
        self.assertEqual(
            consumed_helpers,
            [
                "appendDiagnosticsBridgeButton",
                "appendDiagnosticsBridgeGroupedButtons",
                "diagnosticsBridgeActionLabel",
                "diagnosticsBridgeActions",
                "diagnosticsBridgeHandoffLines",
                "diagnosticsBridgeOrderedActions",
                "diagnosticsBridgeRowTrustLines",
            ],
        )
        for name in consumed_helpers:
            _assert_namespace_export(self, diagnostics_bridge_js, "mediaPipelineDiagnosticsBridge", name)
            self.assertNotIn(f"window.{name} = {name}", diagnostics_bridge_js)

    def test_static_page_scoped_ids_remain_in_their_own_pages(self) -> None:
        desktop_root = find_repo_root(Path(__file__))
        static_root = desktop_root / "apps" / "desktop" / "webview" / "static"
        html = _render_static_index_html(static_root)
        page_pattern = re.compile(
            r'<section class="page(?:\s+is-visible)?" data-page-panel="([^"]+)">(.*?)(?=\n\s*<section class="page(?:\s+is-visible)?" data-page-panel=|\n\s*</main>)',
            re.S,
        )
        pages = dict(page_pattern.findall(html))
        scoped_prefixes = {
            "completed-": "completed",
            "pending-": "pending",
            "rename-": "rename",
            "failure-": "reports",
            "audit-preview-": "reports",
            "report-": "reports",
            "schedule-": "schedule",
            "maintenance-": "maintenance",
            "release-dry-run-": "maintenance",
            "release-build-": "maintenance",
            "backfill-": "maintenance",
            "dependency-atlas-": "maintenance",
            "diagnostics-": "diagnostics",
            "settings-network-": "network",
            "settings-library-": "libraries",
            "settings-libraries-": "libraries",
            "settings-": "settings",
            "cpu-": "live",
            "gpu-": "live",
            "ram-": "live",
        }
        id_locations: dict[str, str] = {}
        for page_name, body in pages.items():
            for node_id in re.findall(r'id="([^"]+)"', body):
                id_locations[node_id] = page_name

        misplaced = {}
        for node_id, page_name in id_locations.items():
            for prefix, expected_page in scoped_prefixes.items():
                if node_id.startswith(prefix):
                    if page_name != expected_page:
                        misplaced[node_id] = {"actual": page_name, "expected": expected_page}
                    break

        self.assertEqual(misplaced, {})

    def test_headless_local_api_backend_builds_bootstrap_payload(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            app_root = Path(raw_root) / "apps" / "desktop"
            app_root.mkdir(parents=True)
            emitted_progress: list[dict[str, object]] = []
            service, resolved, server = build_backend(
                app_root=app_root,
                token="headless-token",
                startup_progress_callback=emitted_progress.append,
            )
            try:
                server.start()
                payload = bootstrap_payload(server, resolved, include_token=True)
            finally:
                server.stop()
                service.stop_background_tasks()
                for handler in list(service.logger.handlers):
                    service.logger.removeHandler(handler)
                    handler.close()

        self.assertEqual(payload["schema_version"], BOOTSTRAP_SCHEMA_VERSION)
        self.assertEqual(payload["token"], "headless-token")
        self.assertTrue(str(payload["url"]).startswith("http://127.0.0.1:"))
        self.assertEqual(Path(str(payload["config_path"])).name, "MediaPipeline_config.psd1")
        self.assertEqual(payload["shell_surface"], "webview")
        self.assertEqual(payload["startup_progress"]["schema_version"], "desktop_startup_progress.v1")
        self.assertTrue(payload["startup_progress"]["steps"])
        self.assertGreaterEqual(len(emitted_progress), 1)
        self.assertEqual(emitted_progress[-1]["schema_version"], "desktop_startup_progress.v1")
        steps_by_id = {step["id"]: step for step in payload["startup_progress"]["steps"]}
        self.assertIn("resolve_app_root", steps_by_id)
        self.assertIn("verify_ffmpeg", steps_by_id)
        self.assertIn("verify_ffprobe", steps_by_id)
        self.assertIn("verify_mkvmerge", steps_by_id)
        self.assertIn("create_local_api", steps_by_id)
        elapsed_values = [float(step["elapsed_ms"]) for step in payload["startup_progress"]["steps"]]
        self.assertEqual(elapsed_values, sorted(elapsed_values))
        self.assertTrue(all(float(step["duration_ms"]) >= 0 for step in payload["startup_progress"]["steps"]))
        for step_id in ("verify_ffmpeg", "verify_ffprobe", "verify_mkvmerge"):
            detail = str(steps_by_id[step_id].get("detail") or "")
            self.assertIn("ops\\pipeline\\tools", detail)
            self.assertNotIn("entrypoints\\Tools", detail)


if __name__ == "__main__":
    unittest.main()
