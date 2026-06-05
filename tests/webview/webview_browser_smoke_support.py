from __future__ import annotations

import hashlib
import json
import shutil
import socket
import subprocess
import textwrap
import time
import unittest
from pathlib import Path

_TRANSIENT_NATIVE_CRASH_RETURN_CODES = {3221226505, -1073740791}
_TRANSIENT_CDP_OPEN_STDERR_FRAGMENTS = (
    "[object ErrorEvent]",
    "CDP websocket error while opening",
)
_MEDIA_NO_MUTATION_SUFFIXES = (
    ".mkv",
    ".mp4",
    ".m4v",
    ".mov",
    ".avi",
    ".srt",
    ".ass",
    ".ssa",
    ".vtt",
    ".pipeline.json",
    ".manifest.json",
    ".jsonl",
)


def find_browser() -> str | None:
    for command in ("chrome", "msedge", "chromium"):
        found = shutil.which(command)
        if found:
            return found
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_media_no_mutation_snapshot(root: Path) -> dict[str, dict[str, object]]:
    """Hash source/output media and sidecar-like artifacts in a smoke fixture."""
    root = Path(root)
    snapshot: dict[str, dict[str, object]] = {"__root__": {"path": str(root)}}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: str(item).casefold()):
        folded = path.name.casefold()
        if not any(folded.endswith(suffix) for suffix in _MEDIA_NO_MUTATION_SUFFIXES):
            continue
        snapshot[str(path)] = {
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
    return snapshot


def assert_media_no_mutation(test_case: unittest.TestCase, before: dict[str, dict[str, object]]) -> None:
    """Fail if a browser smoke changed, deleted, or created media/sidecar files."""
    root = Path(str(before.get("__root__", {}).get("path", "")))
    expected = {path: value for path, value in before.items() if path != "__root__"}
    for raw_path in before:
        if raw_path == "__root__":
            continue
        path = Path(raw_path)
        test_case.assertTrue(path.exists(), f"Watched media/sidecar file was deleted: {path}")
    after = {path: value for path, value in capture_media_no_mutation_snapshot(root).items() if path != "__root__"}
    test_case.assertEqual(after, expected)


def bounded_text(value: object, *, limit: int = 8000) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n... <truncated {len(text) - limit} chars>"


def browser_smoke_failure_message(label: str, result: subprocess.CompletedProcess[str]) -> str:
    return (
        f"{label} failed.\n"
        f"Return code: {result.returncode}\n"
        f"STDOUT:\n{bounded_text(result.stdout)}\n"
        f"STDERR:\n{bounded_text(result.stderr)}"
    )


def assert_browser_smoke_process_ok(label: str, result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode == 0:
        return
    raise AssertionError(browser_smoke_failure_message(label, result))


def _is_transient_browser_runner_crash(result: subprocess.CompletedProcess[str]) -> bool:
    if (result.stdout or "").strip():
        return False
    stderr = (result.stderr or "").strip()
    if result.returncode in _TRANSIENT_NATIVE_CRASH_RETURN_CODES and not stderr:
        return True
    return result.returncode == 1 and any(fragment in stderr for fragment in _TRANSIENT_CDP_OPEN_STDERR_FRAGMENTS)


def run_node_browser_smoke(
    label: str,
    *,
    node: str,
    runner_path: Path,
    payload_path: Path,
    timeout_seconds: int,
) -> dict[str, object]:
    attempts: list[subprocess.CompletedProcess[str]] = []
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                [node, str(runner_path), str(payload_path)],
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            result = subprocess.CompletedProcess(
                error.cmd,
                124,
                stdout="" if error.stdout is None else str(error.stdout),
                stderr=(
                    ("" if error.stderr is None else str(error.stderr))
                    + f"\nTimed out after {timeout_seconds}s."
                ),
            )
            raise AssertionError(browser_smoke_failure_message(label, result)) from error
        attempts.append(result)
        if not _is_transient_browser_runner_crash(result):
            break
        if attempt < max_attempts - 1:
            time.sleep(0.5)

    if len(attempts) > 1 and result.returncode != 0:
        result.stderr = (
            result.stderr
            + f"\nRetried {len(attempts) - 1} time(s) after transient browser runner/CDP startup failure "
            + f"(return code {attempts[0].returncode})."
        )
    assert_browser_smoke_process_ok(label, result)
    lines = result.stdout.strip().splitlines()
    if not lines:
        empty = subprocess.CompletedProcess(
            result.args,
            result.returncode,
            stdout=result.stdout,
            stderr=result.stderr + "\nSmoke runner produced no JSON result line.",
        )
        raise AssertionError(browser_smoke_failure_message(label, empty))
    try:
        parsed = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        malformed = subprocess.CompletedProcess(
            result.args,
            result.returncode,
            stdout=result.stdout,
            stderr=result.stderr + f"\nLast stdout line was not JSON: {error}",
        )
        raise AssertionError(browser_smoke_failure_message(label, malformed)) from error
    if not isinstance(parsed, dict):
        malformed = subprocess.CompletedProcess(
            result.args,
            result.returncode,
            stdout=result.stdout,
            stderr=result.stderr + "\nSmoke runner JSON result was not an object.",
        )
        raise AssertionError(browser_smoke_failure_message(label, malformed))
    return parsed


def browser_cdp_runner_prelude() -> str:
    return textwrap.dedent(
        r"""
        const fs = require("fs");
        const http = require("http");
        const { spawn } = require("child_process");

        const payload = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

        function sleep(ms) {
          return new Promise((resolve) => setTimeout(resolve, ms));
        }

        function httpJson(url) {
          return new Promise((resolve, reject) => {
            const request = http.request(url, { method: "GET" }, (response) => {
              let body = "";
              response.setEncoding("utf8");
              response.on("data", (chunk) => { body += chunk; });
              response.on("end", () => {
                if (response.statusCode < 200 || response.statusCode >= 300) {
                  reject(new Error(`HTTP ${response.statusCode} from ${url}: ${body.slice(0, 500)}`));
                  return;
                }
                try {
                  resolve(JSON.parse(body));
                } catch (error) {
                  reject(error);
                }
              });
            });
            request.on("error", reject);
            request.end();
          });
        }

        async function waitForPageWebSocket(port, targetUrl) {
          const deadline = Date.now() + 15000;
          let lastError = null;
          while (Date.now() < deadline) {
            try {
              const targets = await httpJson(`http://127.0.0.1:${port}/json/list`);
              const pages = targets.filter((target) => target.type === "page" && target.webSocketDebuggerUrl);
              const exact = pages.find((target) => String(target.url || "").startsWith(targetUrl));
              const page = exact || pages[0];
              if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
            } catch (error) {
              lastError = error;
            }
            await sleep(150);
          }
          throw new Error(`Timed out waiting for browser page websocket. Last error: ${lastError ? lastError.message : "none"}`);
        }

        function launchBrowser(args) {
          return spawn(payload.browserPath, args, { stdio: ["ignore", "ignore", "ignore"] });
        }

        async function terminateBrowser(browser) {
          if (!browser) return;
          if (browser.exitCode !== null || browser.signalCode !== null) return;
          const exited = new Promise((resolve) => browser.once("exit", resolve));
          try {
            if (!browser.killed) browser.kill();
          } catch (_) {}
          await Promise.race([exited, sleep(2500)]);
          if (browser.exitCode === null && browser.signalCode === null) {
            try { browser.kill("SIGKILL"); } catch (_) {}
            await Promise.race([
              new Promise((resolve) => browser.once("exit", resolve)),
              sleep(1000),
            ]);
          }
        }

        const MEDIA_PIPELINE_NAMESPACE_PROMOTION = `
        (function () {
          Object.keys(window)
            .filter((key) => key.startsWith("mediaPipeline"))
            .forEach((namespace) => {
              const namespaceExports = window[namespace];
              if (!namespaceExports || typeof namespaceExports !== "object") return;
              Object.entries(namespaceExports).forEach(([name, value]) => {
                if (window[name] === undefined) window[name] = value;
              });
            });
        })();
        `;

        function createCdpClient(wsUrl) {
          let nextId = 1;
          const pending = new Map();
          const consoleEvents = [];
          const exceptions = [];
          const socket = new WebSocket(wsUrl);

          socket.addEventListener("message", (event) => {
            const message = JSON.parse(event.data);
            if (message.id && pending.has(message.id)) {
              const { resolve, reject } = pending.get(message.id);
              pending.delete(message.id);
              if (message.error) reject(new Error(`${message.error.message}: ${message.error.data || ""}`));
              else resolve(message.result || {});
              return;
            }
            if (message.method === "Runtime.consoleAPICalled") {
              const type = message.params?.type || "log";
              const text = (message.params?.args || []).map((arg) => arg.value || arg.description || "").join(" ");
              consoleEvents.push(`${type}:${text}`);
            }
            if (message.method === "Runtime.exceptionThrown") {
              const detail = message.params?.exceptionDetails || {};
              const exception = detail.exception || {};
              exceptions.push(exception.description || exception.value || detail.text || "exception");
            }
            if (message.method === "Log.entryAdded") {
              const entry = message.params?.entry || {};
              if (["error", "warning"].includes(entry.level)) {
                consoleEvents.push(`${entry.level}:${entry.text || ""}`);
              }
            }
          });

          const opened = new Promise((resolve, reject) => {
            socket.addEventListener("open", resolve, { once: true });
            socket.addEventListener("error", () => reject(new Error(`CDP websocket error while opening ${wsUrl}`)), { once: true });
          });

          async function send(method, params = {}) {
            await opened;
            if (method === "Runtime.evaluate" && typeof params.expression === "string") {
              params = {
                ...params,
                expression: `${MEDIA_PIPELINE_NAMESPACE_PROMOTION}\n${params.expression}`,
              };
            }
            const id = nextId++;
            const promise = new Promise((resolve, reject) => {
              pending.set(id, { resolve, reject });
            });
            socket.send(JSON.stringify({ id, method, params }));
            return promise;
          }

          return {
            send,
            consoleEvents,
            exceptions,
            close() {
              try { socket.close(); } catch (_) {}
            },
          };
        }
        """
    )
