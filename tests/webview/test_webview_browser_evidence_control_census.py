from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.core.audit.sources import update_audit_sources

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
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
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )


SURFACE_COUNTS = {
    "completed": 37,
    "pending": 31,
    "reports": 87,
    "network": 82,
}

GENERATED_INSTANCE_COUNTS = {
    "completed": 243,
    "pending": 135,
    "reports": 198,
    "network": 139,
}

EXPECTED_STATUS_COUNTS = {
    "activated": 881,
    "skipped": 37,
    "blocked": 34,
    "failed": 0,
    "discovered": 952,
    "unclassified": 0,
}

GENERATED_FAMILY_COUNT = 149

INTERACTIVE_ROLES = {
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


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


class _StaticControlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.controls: list[dict[str, object]] = []
        self._stack: list[dict[str, object] | None] = []

    @staticmethod
    def _is_control(tag: str, attrs: dict[str, str | None]) -> bool:
        role = str(attrs.get("role") or "").lower()
        tabindex = attrs.get("tabindex")
        numeric_tabindex = False
        try:
            numeric_tabindex = int(str(tabindex)) >= 0
        except (TypeError, ValueError):
            pass
        return (
            tag in {"button", "input", "select", "textarea", "summary"}
            or (tag == "a" and "href" in attrs)
            or role in INTERACTIVE_ROLES
            or numeric_tabindex
        ) and tag != "option"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        record: dict[str, object] | None = None
        if self._is_control(tag, attr_map):
            match_attrs = {
                key: "" if value is None else value
                for key, value in attr_map.items()
                if key == "id"
                or key == "role"
                or key == "tabindex"
                or key == "type"
                or key.startswith("data-")
            }
            record = {
                "tag": tag,
                "attrs": match_attrs,
                "line": self.getpos()[0],
                "text": "",
            }
            self.controls.append(record)
        self._stack.append(record)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, _tag: str) -> None:
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        for record in reversed(self._stack):
            if record is not None:
                record["text"] = str(record["text"]) + data
                break


def _static_control_manifest() -> list[dict[str, object]]:
    manifest: list[dict[str, object]] = []
    for surface, expected_count in SURFACE_COUNTS.items():
        path = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / f"page-{surface}.html"
        parser = _StaticControlParser()
        parser.feed(path.read_text(encoding="utf-8"))
        if len(parser.controls) != expected_count:
            raise AssertionError(f"{surface} static control count changed: {len(parser.controls)} != {expected_count}")
        signature_counts: Counter[str] = Counter()
        for index, record in enumerate(parser.controls, start=1):
            attrs = dict(record["attrs"])
            text = _normalized_text(str(record["text"]))
            signature_payload = {
                "tag": record["tag"],
                "attrs": attrs,
                "text": text if record["tag"] == "summary" or not attrs else "",
            }
            signature = json.dumps(signature_payload, sort_keys=True, separators=(",", ":"))
            occurrence = signature_counts[signature]
            signature_counts[signature] += 1
            semantic = str(attrs.get("id") or "")
            if not semantic:
                semantic = next(
                    (f"{key}={value}" for key, value in attrs.items() if key.startswith("data-") and value),
                    f"{record['tag']}={text or 'control'}",
                )
            manifest.append(
                {
                    "surface": surface,
                    "index": index,
                    "stable_id": f"{surface}:{index:03d}:{semantic}",
                    "tag": record["tag"],
                    "attrs": attrs,
                    "text": text if record["tag"] == "summary" or not attrs else "",
                    "occurrence": occurrence,
                    "line": record["line"],
                }
            )
    return manifest


def _seed_reports_fixture(resolved: object, root: Path, source: Path) -> None:
    failure_payload = [
        {
            "SourcePath": str(source),
            "JobId": "job-census-encode",
            "Stage": "encode",
            "Reason": "Disposable census failure evidence",
            "Classification": "operator_required",
            "ErrorCode": "CENSUS_FIXTURE_FAILURE",
            "RecordedAt": "2026-07-13T12:00:00-04:00",
            "RetryCount": 1,
            "RetryLimit": 3,
        }
    ]
    (root / "failures.json").write_text(json.dumps(failure_payload), encoding="utf-8")
    failure_markers = root / "State" / "Failed" / "Markers"
    failure_markers.mkdir(parents=True, exist_ok=True)
    (failure_markers / "census-marker.json").write_text(
        json.dumps(
            {
                "source_full_path": str(source),
                "job_id": "job-census-publish",
                "stage": "publish",
                "reason": "Disposable census marker evidence",
                "classification": "transient",
                "error_code": "CENSUS_MARKER_FAILURE",
                "recorded_at": "2026-07-13T12:05:00-04:00",
                "retry_count": 1,
                "retry_limit": 5,
            }
        ),
        encoding="utf-8",
    )
    resolved.failed_markers_path = failure_markers

    fieldnames = [
        "Path",
        "RelativePath",
        "LookupTitle",
        "MediaType",
        "EffectiveBucket",
        "PriorityFixLevel",
        "PriorityScore",
        "PrimaryIssueCode",
        "PrimarySuggestedAction",
        "IssueMessages",
    ]
    for filename, bucket, score in (
        ("audit_summary_latest.csv", "RERUN_PIPELINE", "75"),
        ("audit_priority_latest.csv", "REVIEW", "99"),
    ):
        with (root / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(
                {
                    "Path": str(source),
                    "RelativePath": str(source.relative_to(root / "TV")),
                    "LookupTitle": "Serial Experiments Lain",
                    "MediaType": "TV",
                    "EffectiveBucket": bucket,
                    "PriorityFixLevel": "HIGH",
                    "PriorityScore": score,
                    "PrimaryIssueCode": "subtitle_srt_required",
                    "PrimarySuggestedAction": "Rerun pipeline.",
                    "IssueMessages": "Preferred-language SRT missing.",
                }
            )

    update_result = update_audit_sources(
        resolved,
        {"action": "add", "path": str(root / "TV"), "label": "Disposable TV fixture", "enabled": True},
    )
    if not update_result.get("ok"):
        raise AssertionError(f"Could not seed disposable audit source: {update_result}")


def _runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function evidenceControlCensusScript() {
          return `
          (async () => {
            const fixture = window.__MEDIA_PIPELINE_EVIDENCE_CENSUS_FIXTURE || {};
            const manifest = fixture.staticManifest || [];
            const interactiveRoles = new Set([
              "button", "link", "checkbox", "radio", "switch", "tab", "menuitem",
              "menuitemcheckbox", "menuitemradio", "option", "treeitem", "gridcell", "row",
            ]);
            const waitFor = async (predicate, label, timeoutMs = 20000) => {
              const deadline = Date.now() + timeoutMs;
              let lastError = null;
              while (Date.now() < deadline) {
                try { if (await predicate()) return; } catch (error) { lastError = error; }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : ""));
            };
            const norm = (value) => String(value || "").replace(/\\s+/g, " ").trim();
            const isInteractive = (element) => {
              const tag = String(element?.tagName || "").toLowerCase();
              if (["button", "input", "select", "textarea", "summary"].includes(tag)) return tag !== "option";
              if (tag === "a" && element.hasAttribute("href")) return true;
              if (interactiveRoles.has(String(element?.getAttribute?.("role") || "").toLowerCase())) return tag !== "option";
              const rawTabIndex = element?.getAttribute?.("tabindex");
              return rawTabIndex !== null && Number.isFinite(Number(rawTabIndex)) && Number(rawTabIndex) >= 0;
            };
            const interactiveDescendants = (root) => Array.from(root?.querySelectorAll?.("*") || []).filter(isInteractive);
            const elementDescriptor = (element) => {
              const dataset = {};
              Array.from(element.attributes || []).forEach((attr) => {
                if (attr.name.startsWith("data-")) dataset[attr.name] = attr.value;
              });
              const container = element.closest("tbody[id], [id]");
              const table = element.closest("table");
              return {
                tag: String(element.tagName || "").toLowerCase(),
                id: element.id || "",
                type: element.getAttribute("type") || "",
                role: element.getAttribute("role") || "",
                tabindex: element.getAttribute("tabindex"),
                className: typeof element.className === "string" ? element.className : "",
                text: norm(element.textContent).slice(0, 120),
                ariaLabel: element.getAttribute("aria-label") || "",
                disabled: Boolean(element.disabled),
                readOnly: Boolean(element.readOnly),
                dataset,
                containerId: container?.id || "",
                tableLabel: table?.getAttribute("aria-label") || table?.id || "",
              };
            };
            const generatedLocatorKey = (descriptor) => {
              const volatileDatasetKeys = new Set([
                "data-state", "data-status", "data-sort-direction", "data-open-target-available",
                "data-open-target-base-title", "data-selected", "data-active", "data-row-key",
              ]);
              const dataset = Object.fromEntries(Object.entries(descriptor.dataset || {}).filter(
                ([key]) => !volatileDatasetKeys.has(key)
              ));
              const stableClasses = String(descriptor.className || "").split(/\\s+/).filter(
                (value) => value && !["active", "is-active", "is-selected", "selected", "disabled"].includes(value)
              );
              const isSelectableRow = descriptor.role === "row" || "data-selectable-row" in dataset;
              const isSortButton = stableClasses.includes("table-sort-button");
              const hasActionIdentity = Object.keys(dataset).some(
                (key) => !["data-row-key", "data-selectable-row", "data-ui-quick-link"].includes(key)
              );
              return JSON.stringify({
                tag: descriptor.tag,
                id: descriptor.id,
                type: descriptor.type,
                role: descriptor.role,
                tabindex: descriptor.tabindex,
                className: stableClasses.join(" "),
                text: isSelectableRow || hasActionIdentity ? "" : descriptor.text,
                ariaLabel: isSortButton || hasActionIdentity ? "" : descriptor.ariaLabel,
                dataset,
                containerId: hasActionIdentity ? "" : descriptor.containerId,
                tableLabel: descriptor.tableLabel,
              });
            };
            const generatedFamily = (surface, descriptor) => {
              const datasetKeys = Object.keys(descriptor.dataset || {}).sort();
              if (datasetKeys.length) return surface + ":data:" + datasetKeys.join("+");
              if (descriptor.role === "row") return surface + ":row:" + (descriptor.containerId || "unscoped");
              if (descriptor.className.includes("table-sort-button")) return surface + ":table-sort";
              if (descriptor.className.includes("table-column-resizer")) return surface + ":table-resize";
              if (descriptor.className.includes("pcb-btn-")) {
                return surface + ":panel-customization:" + descriptor.className.split(/\\s+/).find((value) => value.startsWith("pcb-btn-"));
              }
              if (descriptor.tag === "input" && descriptor.tableLabel) return surface + ":table-column-visibility";
              if (descriptor.tag === "summary") return surface + ":summary:" + descriptor.text;
              return surface + ":generated:" + descriptor.tag + ":" + (descriptor.text || descriptor.ariaLabel || descriptor.className || "control");
            };
            const skippedStatic = new Map([
              ["completed:019", ["destructive", "Final-library promotion mutates published output state."]],
              ["completed:022", ["destructive", "Confirmed manifest reconciliation writes backend state."]],
              ["completed:024", ["destructive", "Confirmed sidecar repair writes a media sidecar."]],
              ["completed:026", ["destructive", "Final-library batch promotion moves reviewed outputs."]],
              ["completed:027", ["blocked-future", "Promotion pause is unavailable outside an active promotion."]],
              ["completed:028", ["blocked-future", "Promotion resume is unavailable outside a paused promotion."]],
              ["pending:002", ["destructive", "Pending drain moves parked output payloads."]],
              ["pending:020", ["destructive", "Pending drain moves parked output payloads."]],
              ["pending:028", ["destructive", "Confirmed manifest repair writes pending-publish state."]],
              ["pending:030", ["destructive", "Confirmed orphan reconciliation writes pending-publish state."]],
              ["reports:025", ["destructive", "Failure artifact cleanup deletes backend evidence files."]],
              ["reports:038", ["destructive", "Failure clear moves marker evidence."]],
              ["reports:043", ["destructive", "Failure archive moves evidence files."]],
              ["reports:044", ["state-mutation", "Failure acknowledgement writes the resolution journal."]],
              ["reports:045", ["state-mutation", "Failure work-start writes the resolution journal."]],
              ["reports:046", ["state-mutation", "Failure resolution writes the resolution journal."]],
              ["reports:047", ["state-mutation", "Failure reopen writes the resolution journal."]],
              ["reports:058", ["process-lifecycle", "Audit start launches a child process and scans media roots."]],
              ["reports:059", ["process-lifecycle", "Audit stop changes child-process lifecycle state."]],
              ["reports:074", ["state-mutation", "Audit ignore writes the ignore manifest."]],
              ["reports:075", ["queue-mutation", "CSV rerun export writes queue input state."]],
              ["reports:085", ["settings-mutation", "Score policy save persists backend policy state."]],
              ["network:003", ["process-lifecycle", "Coordinator start changes process lifecycle state."]],
              ["network:004", ["process-lifecycle", "Coordinator stop changes process lifecycle state."]],
              ["network:007", ["external-network", "Connection test reaches a configured coordinator URL."]],
              ["network:008", ["process-lifecycle", "Worker start changes process lifecycle state."]],
              ["network:009", ["process-lifecycle", "Worker stop changes process lifecycle state."]],
              ["network:026", ["secret-transfer", "Join-blob creation creates or rotates a shared secret."]],
              ["network:030", ["settings-mutation", "Join import persists coordinator settings and a token."]],
              ["network:031", ["external-network", "Coordinator discovery performs network discovery."]],
              ["network:033", ["process-lifecycle", "Lifecycle confirmation can submit a start/stop command."]],
              ["network:053", ["settings-mutation", "Distributed settings save persists backend config."]],
              ["network:068", ["settings-mutation", "Role setup save persists backend config."]],
            ]);
            const blockedStatic = new Map([
              ["network:028", ["readonly", "Generated join blob output is read-only."]],
              ["network:044", ["derived-hidden", "JSON path-map mirror is hidden behind the structured editor."]],
              ["network:062", ["derived-hidden", "Role-setup JSON path-map mirror is hidden behind the structured editor."]],
              ["network:077", ["disabled-future", "Future Drain control is intentionally disabled."]],
              ["network:078", ["disabled-future", "Future Disable New Work control is intentionally disabled."]],
              ["network:079", ["disabled-future", "Future Pause control is intentionally disabled."]],
              ["network:080", ["disabled-future", "Future Abort Current control is intentionally disabled."]],
              ["network:081", ["disabled-future", "Future Reclaim Job control is intentionally disabled."]],
              ["network:082", ["disabled-future", "Future Quarantine Worker control is intentionally disabled."]],
            ]);
            const actionResults = [];
            const apiPosts = [];
            const apiGets = [];
            const confirmations = [];
            const originalApiGet = window.mediaPipelineApi?.apiGet || window.apiGet;
            const originalApiPost = window.mediaPipelineApi?.apiPost || window.apiPost;
            if (typeof originalApiGet !== "function" || typeof originalApiPost !== "function") {
              throw new Error("Local API clients were not available to the census.");
            }
            const trackedApiGet = async (path, options) => {
              apiGets.push({ path: String(path || ""), options: options || {} });
              return originalApiGet(path, options);
            };
            const trackedApiPost = async (path, body, options) => {
              if (String(path || "") !== "/api/ui-preferences") {
                apiPosts.push({ path: String(path || ""), body: body || {}, options: options || {} });
              }
              return originalApiPost(path, body, options);
            };
            window.apiGet = trackedApiGet;
            window.apiPost = trackedApiPost;
            if (window.mediaPipelineApi) {
              window.mediaPipelineApi.apiGet = trackedApiGet;
              window.mediaPipelineApi.apiPost = trackedApiPost;
            }
            window.confirm = (message) => {
              confirmations.push(String(message || ""));
              return false;
            };

            const eventProof = async (element, eventName, dispatch) => {
              let observed = false;
              element.addEventListener(eventName, () => { observed = true; }, { once: true, capture: true });
              dispatch();
              await Promise.resolve();
              if (!observed) throw new Error("DOM did not observe " + eventName);
            };
            const activateElement = async (element, surface) => {
              if (!element?.isConnected) throw new Error("control is no longer connected");
              window.showPage(surface);
              const tag = String(element.tagName || "").toLowerCase();
              const type = String(element.getAttribute("type") || "").toLowerCase();
              if (tag === "input" && ["checkbox", "radio"].includes(type)) {
                const original = Boolean(element.checked);
                await eventProof(element, "click", () => element.click());
                if (type === "checkbox" && Boolean(element.checked) !== original) element.click();
                return "click";
              }
              if (["input", "textarea"].includes(tag)) {
                const original = element.value;
                const replacement = type === "number"
                  ? String(Number.isFinite(Number(original)) ? Number(original) : Number(element.min || 0))
                  : String(original || "census");
                element.value = replacement;
                await eventProof(element, "input", () => element.dispatchEvent(new Event("input", { bubbles: true })));
                element.dispatchEvent(new Event("change", { bubbles: true }));
                element.value = original;
                element.dispatchEvent(new Event("input", { bubbles: true }));
                element.dispatchEvent(new Event("change", { bubbles: true }));
                return "input";
              }
              if (tag === "select") {
                const original = element.value;
                const next = Array.from(element.options || []).find((option) => !option.disabled && option.value !== original);
                if (next) element.value = next.value;
                await eventProof(element, "change", () => element.dispatchEvent(new Event("change", { bubbles: true })));
                element.value = original;
                element.dispatchEvent(new Event("change", { bubbles: true }));
                return "change";
              }
              if (element.classList?.contains("table-column-resizer")) {
                await eventProof(element, "keydown", () => element.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
                element.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
                return "keydown";
              }
              await eventProof(element, "click", () => element.click());
              if (
                tag === "summary"
                || element.classList?.contains("pcb-btn-advanced")
                || element.classList?.contains("pcb-btn-hidden")
                || element.classList?.contains("summary-toggle")
                || ["Customize", "Show Advanced", "Hide Advanced", "Show Evidence", "Hide Evidence"].includes(norm(element.textContent))
              ) {
                element.click();
              }
              if (tag === "button" && (
                element.id
                || Object.keys(element.dataset || {}).some((key) => !["state", "sortDirection"].includes(key))
              )) {
                await new Promise((resolve) => setTimeout(resolve, 180));
              }
              return "click";
            };

            await waitFor(
              () => window.performance?.getEntriesByName?.("mediapipeline-startup-critical-ready")?.length > 0
                && typeof window.showPage === "function"
                && typeof window.refreshAllNow === "function",
              "startup critical refresh",
            );
            for (const surface of ["completed", "pending", "reports", "network"]) {
              window.showPage(surface);
              await window.refreshAllNow({ page: surface, reason: "evidence-control-census" });
              await new Promise((resolve) => setTimeout(resolve, 200));
            }
            document.querySelector("#completed-history-rows tr[data-row-key]:last-child")?.click();
            document.querySelector("#pending-rows tr[data-row-key]")?.click();
            document.querySelector("#failure-rows tr[data-row-key]")?.click();
            document.querySelector("#audit-preview-rows tr[data-row-key]")?.click();
            document.querySelector('#report-audit-source-rows input[type="checkbox"]')?.click();
            document.querySelector("#network-worker-rows tr[data-row-key]")?.click();
            await new Promise((resolve) => setTimeout(resolve, 200));

            const locateStatic = (entry) => {
              const panel = document.querySelector('[data-page-panel="' + entry.surface + '"]');
              if (!panel) return null;
              let candidates = Array.from(panel.querySelectorAll(entry.tag));
              candidates = candidates.filter((element) => Object.entries(entry.attrs || {}).every(
                ([name, value]) => (element.getAttribute(name) || "") === String(value || "")
              ));
              if (entry.text) candidates = candidates.filter((element) => norm(element.textContent) === entry.text);
              return candidates[Number(entry.occurrence || 0)] || null;
            };
            const staticRecords = [];
            const staticPairs = [];
            const matchedElements = new Set();
            const missingStatic = [];
            for (const entry of manifest) {
              const element = locateStatic(entry);
              if (!element) {
                missingStatic.push({ stableId: entry.stable_id, reason: "authored control not rendered" });
                continue;
              }
              matchedElements.add(element);
              staticPairs.push({ entry, element });
              staticRecords.push({
                stableId: entry.stable_id,
                surface: entry.surface,
                sourceLine: entry.line,
                descriptor: elementDescriptor(element),
              });
            }

            const generatedRecords = [];
            const generatedPairs = [];
            for (const surface of ["completed", "pending", "reports", "network"]) {
              const panel = document.querySelector('[data-page-panel="' + surface + '"]');
              const locatorCounts = new Map();
              interactiveDescendants(panel).forEach((element, index) => {
                const descriptor = elementDescriptor(element);
                const locatorKey = generatedLocatorKey(descriptor);
                const locatorOccurrence = Number(locatorCounts.get(locatorKey) || 0);
                locatorCounts.set(locatorKey, locatorOccurrence + 1);
                if (matchedElements.has(element)) return;
                const stableId = surface + ":generated-instance:" + String(index + 1).padStart(3, "0");
                generatedPairs.push({ stableId, surface, locatorKey, locatorOccurrence, descriptor });
                generatedRecords.push({
                  stableId,
                  surface,
                  family: generatedFamily(surface, descriptor),
                  descriptor,
                });
              });
            }

            const generatedById = new Map(generatedRecords.map((record) => [record.stableId, record]));
            const staticById = new Map(staticRecords.map((record) => [record.stableId, record]));
            const locateGenerated = (pair) => {
              const panel = document.querySelector('[data-page-panel="' + pair.surface + '"]');
              const dataset = pair.descriptor?.dataset || {};
              const directOpenAttribute = "data-open-completed" in dataset
                ? "data-open-completed"
                : "data-open-pending" in dataset
                  ? "data-open-pending"
                  : "";
              if (directOpenAttribute) {
                return Array.from(panel?.querySelectorAll?.("[" + directOpenAttribute + "]") || []).find(
                  (element) => element.getAttribute(directOpenAttribute) === dataset[directOpenAttribute]
                ) || null;
              }
              return interactiveDescendants(panel).filter(
                (element) => generatedLocatorKey(elementDescriptor(element)) === pair.locatorKey
              )[pair.locatorOccurrence] || null;
            };
            const resultRecord = (pair, kind, status, classification, reason, extra = {}) => {
              const source = kind === "authored" ? staticById.get(pair.entry.stable_id) : generatedById.get(pair.stableId);
              actionResults.push({
                stableId: kind === "authored" ? pair.entry.stable_id : pair.stableId,
                kind,
                surface: kind === "authored" ? pair.entry.surface : pair.surface,
                family: source?.family || "authored",
                descriptor: source?.descriptor || {},
                status,
                classification,
                reason,
                ...extra,
              });
            };
            const activatePair = async (pair, kind) => {
              const stableId = kind === "authored" ? pair.entry.stable_id : pair.stableId;
              const staticKey = stableId.split(":").slice(0, 2).join(":");
              const source = kind === "authored" ? staticById.get(stableId) : generatedById.get(stableId);
              const descriptor = source?.descriptor || {};
              if (kind === "authored" && skippedStatic.has(staticKey)) {
                const [classification, reason] = skippedStatic.get(staticKey);
                resultRecord(pair, kind, "skipped", classification, reason);
                return;
              }
              if (kind === "authored" && blockedStatic.has(staticKey)) {
                const [classification, reason] = blockedStatic.get(staticKey);
                resultRecord(pair, kind, "blocked", classification, reason);
                return;
              }
              if (kind === "generated") {
                const dataset = descriptor.dataset || {};
                const auditAction = String(dataset["data-audit-source-action"] || "").toLowerCase();
                if ("data-completed-promote-row-key" in dataset || "data-completed-promote-selected" in dataset) {
                  resultRecord(pair, kind, "skipped", "destructive", "Generated promotion action moves reviewed output state.");
                  return;
                }
                if (["remove", "delete", "enable", "disable", "run"].includes(auditAction)) {
                  resultRecord(pair, kind, "skipped", auditAction === "run" ? "process-lifecycle" : "state-mutation", "Generated audit-source action mutates source registry or process state.");
                  return;
                }
                if ("data-network-test-connection" in dataset) {
                  resultRecord(pair, kind, "skipped", "external-network", "Generated connection test can reach a configured coordinator URL.");
                  return;
                }
                if (String(descriptor.className || "").split(/\\s+/).includes("danger-button")) {
                  resultRecord(pair, kind, "skipped", "destructive", "Generated danger action is not safe for a read-only/staging census.");
                  return;
                }
              }
              if (kind === "generated") {
                const dataset = descriptor.dataset || {};
                const contextRow = "data-open-completed" in dataset
                  ? document.querySelector("#completed-history-rows tr[data-row-key]:last-child")
                  : "data-open-pending" in dataset
                    ? document.querySelector("#pending-rows tr[data-row-key]")
                    : null;
                if (contextRow) {
                  contextRow.click();
                  await new Promise((resolve) => setTimeout(resolve, 120));
                }
              }
              let element = kind === "authored" ? locateStatic(pair.entry) : locateGenerated(pair);
              if (!element && kind === "generated") {
                const dataset = descriptor.dataset || {};
                const contextRow = "data-open-completed" in dataset
                  ? document.querySelector("#completed-history-rows tr[data-row-key]:last-child")
                  : "data-open-pending" in dataset
                    ? document.querySelector("#pending-rows tr[data-row-key]")
                    : null;
                if (contextRow) {
                  if (contextRow.getAttribute("aria-selected") !== "true") contextRow.click();
                  await new Promise((resolve) => setTimeout(resolve, 120));
                  element = locateGenerated(pair);
                }
              }
              if (!element) {
                resultRecord(pair, kind, "failed", "unreachable", "Control could not be reacquired after an earlier DOM render.");
                return;
              }
              if (element.disabled) {
                resultRecord(pair, kind, "blocked", "disabled-prerequisite", "Control is disabled in the disposable fixture state.");
                return;
              }
              if (element.readOnly) {
                resultRecord(pair, kind, "blocked", "readonly", "Read-only control cannot accept operator input.");
                return;
              }
              const getStart = apiGets.length;
              const postStart = apiPosts.length;
              const wasVisible = Boolean(element.getClientRects().length);
              try {
                const domEvent = await activateElement(element, kind === "authored" ? pair.entry.surface : pair.surface);
                resultRecord(pair, kind, "activated", "safe-local-readonly-staging", "Actual DOM event completed against the disposable backend fixture.", {
                  domEvent,
                  wasVisible,
                  apiGets: apiGets.slice(getStart).map((entry) => entry.path),
                  apiPosts: apiPosts.slice(postStart).map((entry) => entry.path),
                });
              } catch (error) {
                resultRecord(pair, kind, "failed", "activation-error", String(error?.message || error));
              }
            };

            const generatedActivationPriority = (pair) => {
              const descriptor = generatedById.get(pair.stableId)?.descriptor || {};
              const dataset = descriptor.dataset || {};
              if ("data-open-completed" in dataset || "data-open-pending" in dataset) return 0;
              if (descriptor.role === "row" && ["completed-rows", "pending-rows"].includes(descriptor.containerId)) return 1;
              return 2;
            };
            for (const pair of [...generatedPairs].sort(
              (left, right) => generatedActivationPriority(left) - generatedActivationPriority(right)
            )) await activatePair(pair, "generated");
            for (const pair of staticPairs) await activatePair(pair, "authored");

            const statusCounts = Object.fromEntries(
              ["activated", "skipped", "blocked", "failed"].map(
                (status) => [status, actionResults.filter((record) => record.status === status).length]
              )
            );
            statusCounts.discovered = actionResults.length;
            statusCounts.unclassified = actionResults.filter(
              (record) => !["activated", "skipped", "blocked", "failed"].includes(record.status)
            ).length;
            const forbiddenPostFragments = [
              "/api/final-library/promote", "/api/pending-publish/drain", "/api/failures/clear",
              "/api/failures/archive", "/api/failures/lifecycle", "/api/audit/start", "/api/audit/stop",
              "/api/audit/export-rerun-csv", "/api/network/coordinator/start", "/api/network/coordinator/stop",
              "/api/network/worker/start", "/api/network/worker/stop", "/api/network/join",
              "/api/settings/save",
            ];
            const forbiddenPosts = apiPosts.filter((entry) => forbiddenPostFragments.some(
              (fragment) => String(entry.path || "").includes(fragment)
            ));
            const confirmedPosts = apiPosts.filter((entry) => /"confirm[^" ]*":true/.test(JSON.stringify(entry.body || {})));
            return {
              ok: missingStatic.length === 0 && statusCounts.failed === 0 && statusCounts.unclassified === 0
                && forbiddenPosts.length === 0 && confirmedPosts.length === 0,
              missingStatic,
              staticRecords,
              generatedRecords,
              actionResults,
              statusCounts,
              apiGets,
              apiPosts,
              confirmations,
              forbiddenPosts,
              confirmedPosts,
              surfaceCounts: Object.fromEntries(["completed", "pending", "reports", "network"].map(
                (surface) => [surface, staticRecords.filter((record) => record.surface === surface).length]
              )),
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
            const readyDeadline = Date.now() + 20000;
            while (Date.now() < readyDeadline) {
              try {
                const ready = await client.send("Runtime.evaluate", {
                  expression: `Boolean(document.readyState === "complete" && document.querySelector('[data-page-panel="completed"]') && typeof window.showPage === "function")`,
                  returnByValue: true,
                });
                if (ready.result?.value === true) break;
              } catch (error) {
                if (!String(error?.message || error).includes("Execution context was destroyed")) throw error;
              }
              await sleep(150);
            }
            await client.send("Runtime.evaluate", {
              expression: `window.__MEDIA_PIPELINE_EVIDENCE_CENSUS_FIXTURE = ${JSON.stringify({ staticManifest: payload.staticManifest })}`,
              returnByValue: true,
            });
            const result = await client.send("Runtime.evaluate", {
              expression: evidenceControlCensusScript(), awaitPromise: true, returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            const errors = client.consoleEvents.filter((entry) => entry.startsWith("error:") && !entry.includes("favicon.ico"));
            if (client.exceptions.length || errors.length) throw new Error(client.exceptions.concat(errors).join("; "));
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }
        main().catch((error) => { console.error(error.stack || error.message || String(error)); process.exit(1); });
        """
    )


class WebViewBrowserEvidenceControlCensus(unittest.TestCase):
    def test_disposable_backend_rendered_control_census(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the evidence-control browser census.")
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the evidence-control browser census.")

        static_manifest = _static_control_manifest()
        self.assertEqual(len(static_manifest), 237)

        with tempfile.TemporaryDirectory() as raw_root, tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
            root = Path(raw_root)
            tmp = Path(raw_tmp)
            resolved, source, output = _write_fixture_state(root)
            resolved.local_base = root
            resolved.state_root = root / "State"
            resolved.runtime_state_root = resolved.state_root
            resolved.run_logs_root = root / "RunLogs"
            resolved.app_state_path = root / "desktop_app_state.json"
            resolved.state_root.mkdir(parents=True, exist_ok=True)
            resolved.run_logs_root.mkdir(parents=True, exist_ok=True)
            canonical_completed_sidecar = output.with_suffix(".pipeline.json")
            canonical_completed_sidecar.write_text(
                output.with_name(output.name + ".pipeline.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            _seed_reports_fixture(resolved, root, source)
            appdata_root = root / "Profile" / "MediaPipeline"
            temp_root = root / "Profile" / "Temp"
            temp_root.mkdir(parents=True, exist_ok=True)

            media_snapshots = [
                capture_media_no_mutation_snapshot(root / "TV"),
                capture_media_no_mutation_snapshot(root / "Outsource"),
                capture_media_no_mutation_snapshot(root / "PendingServerPush"),
            ]
            service = DummyWorkflowFacadeService(root)
            service.open_path_with_default_app = service.open_path  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-evidence-control-census-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                command_journal_path=resolved.state_root / "RunLogs" / "local_api_command_history.json",
            )
            server._path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
                "ok": True,
                "canceled": False,
                "selection_mode": "folder",
                "paths": [str(root / "TV")],
                "message": "Disposable fixture folder selected.",
                "errors": [],
            }

            payload_path = tmp / "evidence-control-census-payload.json"
            runner_path = tmp / "evidence-control-census-runner.cjs"
            runner_path.write_text(_runner_source(), encoding="utf-8")
            isolated_environment = {
                "MEDIAPIPELINE_APPDATA_ROOT": str(appdata_root),
                "APPDATA": str(root / "Profile" / "Roaming"),
                "LOCALAPPDATA": str(root / "Profile" / "Local"),
                "TEMP": str(temp_root),
                "TMP": str(temp_root),
            }
            with patch.dict(os.environ, isolated_environment, clear=False):
                try:
                    server.start()
                    payload_path.write_text(
                        json.dumps(
                            {
                                "browserPath": browser_path,
                                "port": free_port(),
                                "tmpRoot": str(tmp),
                                "url": f"{server.url}/",
                                "staticManifest": static_manifest,
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    result = run_node_browser_smoke(
                        "Browser-backed Completed/Pending/Reports/Network evidence-control census",
                        node=node,
                        runner_path=runner_path,
                        payload_path=payload_path,
                        timeout_seconds=180,
                    )
                finally:
                    server.stop()

            for media_snapshot in media_snapshots:
                assert_media_no_mutation(self, media_snapshot)
            self.assertEqual(source.read_bytes(), b"source-media")
            self.assertEqual(output.read_bytes(), b"output-media")
            browser_result = result["result"]
            self.assertTrue(result["ok"])
            self.assertTrue(
                browser_result["ok"],
                json.dumps(
                    {
                        "missing_static": browser_result["missingStatic"],
                        "status_counts": browser_result["statusCounts"],
                        "failed": [
                            record
                            for record in browser_result["actionResults"]
                            if record["status"] == "failed"
                        ],
                        "forbidden_posts": browser_result["forbiddenPosts"],
                        "confirmed_posts": browser_result["confirmedPosts"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
            self.assertEqual(browser_result["surfaceCounts"], SURFACE_COUNTS)
            self.assertEqual(len(browser_result["staticRecords"]), 237)
            generated_surface_counts = Counter(
                record["surface"] for record in browser_result["generatedRecords"]
            )
            self.assertEqual(dict(generated_surface_counts), GENERATED_INSTANCE_COUNTS)
            self.assertEqual(
                len({record["family"] for record in browser_result["generatedRecords"]}),
                GENERATED_FAMILY_COUNT,
            )
            self.assertEqual(
                browser_result["statusCounts"]["discovered"],
                len(browser_result["staticRecords"]) + len(browser_result["generatedRecords"]),
            )
            self.assertEqual(browser_result["statusCounts"], EXPECTED_STATUS_COUNTS)
            self.assertEqual(browser_result["statusCounts"]["failed"], 0, browser_result["actionResults"])
            self.assertEqual(browser_result["statusCounts"]["unclassified"], 0, browser_result["actionResults"])
            self.assertEqual(browser_result["forbiddenPosts"], [])
            self.assertEqual(browser_result["confirmedPosts"], [])
            stable_ids = [record["stableId"] for record in browser_result["actionResults"]]
            self.assertEqual(len(stable_ids), len(set(stable_ids)), "Census stable IDs must be unique.")
            completed_open_actions = [
                record
                for record in browser_result["actionResults"]
                if "data-open-completed" in record["descriptor"]["dataset"]
            ]
            pending_open_actions = [
                record
                for record in browser_result["actionResults"]
                if "data-open-pending" in record["descriptor"]["dataset"]
            ]
            self.assertEqual(
                {record["descriptor"]["dataset"]["data-open-completed"] for record in completed_open_actions},
                {"play_output_file", "output_folder", "sidecar", "source_folder"},
            )
            self.assertEqual(
                {record["descriptor"]["dataset"]["data-open-pending"] for record in pending_open_actions},
                {"play_local_file", "manifest", "destination_folder", "source_folder"},
            )
            self.assertTrue(
                all(record["status"] == "activated" for record in completed_open_actions), completed_open_actions
            )
            self.assertTrue(all(record["status"] == "activated" for record in pending_open_actions), pending_open_actions)
            opened_paths = {str(Path(path).resolve()).casefold() for path in service.opened_paths}
            for expected_path in (
                output,
                output.parent,
                canonical_completed_sidecar,
                source.parent,
                resolved.pending_push_path / output.name,
                resolved.pending_push_path / f"{output.name}.manifest.json",
            ):
                self.assertIn(str(Path(expected_path).resolve()).casefold(), opened_paths)

            command_journal_path = resolved.state_root / "RunLogs" / "local_api_command_history.json"
            self.assertTrue(command_journal_path.exists())
            command_journal = json.loads(command_journal_path.read_text(encoding="utf-8"))
            command_names = [str(entry.get("command") or "") for entry in command_journal.get("entries", [])]
            forbidden_command_fragments = {
                "final_library.promote",
                "pending_publish.drain",
                "failures.clear",
                "failures.archive",
                "failures.lifecycle",
                "audit.start",
                "audit.stop",
                "audit.export_rerun",
                "network.coordinator.start",
                "network.coordinator.stop",
                "network.worker.start",
                "network.worker.stop",
                "network.join",
                "settings.save",
            }
            self.assertFalse(
                [name for name in command_names if any(fragment in name for fragment in forbidden_command_fragments)],
                command_names,
            )
            self.assertEqual(command_names.count("pending_publish.open"), 4, command_names)

            emit_mode = os.environ.get("MEDIAPIPELINE_EMIT_CONTROL_CENSUS")
            if emit_mode:
                evidence_payload: dict[str, object] = {
                    "schema_version": "webview_evidence_control_census.v1",
                    "surface_counts": browser_result["surfaceCounts"],
                    "status_counts": browser_result["statusCounts"],
                    "generated_count": len(browser_result["generatedRecords"]),
                    "generated_family_count": len(
                        {record["family"] for record in browser_result["generatedRecords"]}
                    ),
                }
                if emit_mode == "summary":
                    evidence_payload["per_surface_status_counts"] = {
                        surface: dict(
                            Counter(
                                record["status"]
                                for record in browser_result["actionResults"]
                                if record["surface"] == surface
                            )
                        )
                        for surface in SURFACE_COUNTS
                    }
                    evidence_payload["authored_activated_ids"] = [
                        record["stableId"]
                        for record in browser_result["actionResults"]
                        if record["kind"] == "authored" and record["status"] == "activated"
                    ]
                    evidence_payload["authored_nonactivated_records"] = [
                        {
                            key: record[key]
                            for key in ("stableId", "surface", "status", "classification", "reason")
                        }
                        for record in browser_result["actionResults"]
                        if record["kind"] == "authored" and record["status"] != "activated"
                    ]
                    evidence_payload["generated_nonactivated_records"] = [
                        {
                            key: record[key]
                            for key in ("stableId", "surface", "family", "status", "classification", "reason")
                        }
                        for record in browser_result["actionResults"]
                        if record["kind"] == "generated" and record["status"] != "activated"
                    ]
                else:
                    evidence_payload["records"] = browser_result["actionResults"]
                print(
                    "WEBVIEW_EVIDENCE_CONTROL_CENSUS="
                    + json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True)
                )


if __name__ == "__main__":
    unittest.main()
