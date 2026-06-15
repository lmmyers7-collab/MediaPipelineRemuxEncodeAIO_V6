from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
BRIDGE_PATH = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "tauriLifecycleBridge.js"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is required for Tauri lifecycle bridge smoke tests.")
    return node


class TauriLifecycleBridgeReplayTests(unittest.TestCase):
    def test_replays_event_dispatched_before_app_listener_registration(self) -> None:
        script = textwrap.dedent(
            r"""
            const fs = require("node:fs");
            const vm = require("node:vm");
            const source = fs.readFileSync(__BRIDGE_PATH__, "utf8");
            const listeners = new Map();
            let tauriCallback = null;

            function CustomEvent(type, options = {}) {
              this.type = type;
              this.detail = options.detail;
            }

            const window = {
              __TAURI__: {
                event: {
                  listen: async (name, callback) => {
                    if (name !== "mediapipeline://backend-lifecycle") {
                      throw new Error("unexpected Tauri event name: " + name);
                    }
                    tauriCallback = callback;
                    return () => {};
                  },
                },
              },
              CustomEvent,
              addEventListener(type, listener) {
                const existing = listeners.get(type) || [];
                existing.push(listener);
                listeners.set(type, existing);
              },
              dispatchEvent(event) {
                for (const listener of listeners.get(event.type) || []) {
                  listener(event);
                }
                return true;
              },
            };
            const document = {
              readyState: "complete",
              addEventListener() {
                throw new Error("DOMContentLoaded listener should not be needed in this test.");
              },
            };

            (async () => {
              vm.runInNewContext(source, { window, document, console, CustomEvent }, {
                filename: "tauriLifecycleBridge.js",
              });
              await Promise.resolve();
              await Promise.resolve();
              if (typeof tauriCallback !== "function") {
                throw new Error("Tauri lifecycle listener was not registered.");
              }

              tauriCallback({ payload: { status: "backend_started", runId: "early-event" } });
              let received = null;
              window.addEventListener("mediapipeline:backend-lifecycle", (event) => {
                received = event.detail;
              });

              const bridge = window.mediaPipelineTauriLifecycleBridge;
              if (!bridge || typeof bridge.replayLatestBackendLifecycleEvent !== "function") {
                throw new Error("Lifecycle bridge replay API is missing.");
              }
              if (bridge.eventName !== "mediapipeline:backend-lifecycle") {
                throw new Error("Lifecycle bridge exposes the wrong WebView event name.");
              }
              if (bridge.replayLatestBackendLifecycleEvent() !== true) {
                throw new Error("Expected replay to report a retained lifecycle event.");
              }
              if (!received || received.source !== "mediapipeline://backend-lifecycle") {
                throw new Error("Replay did not deliver the retained lifecycle source.");
              }
              if (!received.payload || received.payload.runId !== "early-event") {
                throw new Error("Replay did not deliver the retained lifecycle payload.");
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exit(1);
            });
            """
        ).replace("__BRIDGE_PATH__", json.dumps(str(BRIDGE_PATH)))

        result = subprocess.run(
            [_node(), "-e", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
