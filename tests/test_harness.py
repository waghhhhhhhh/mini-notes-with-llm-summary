from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEV_SCRIPT = ROOT / "scripts" / "anna-dev.mjs"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class HarnessIntegrationTest(unittest.TestCase):
    process: subprocess.Popen[str]
    base_url: str

    def setUp(self) -> None:
        node = shutil.which("node")
        self.assertIsNotNone(node, "node must be available")
        port = _free_port()
        self.base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env["BROWSER"] = "none"

        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        self.process = subprocess.Popen(
            [node, str(DEV_SCRIPT), "--port", str(port), "--no-watch"],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
        self._wait_until_ready()

    def tearDown(self) -> None:
        if self.process.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    text=True,
                )
            else:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        if self.process.stdout is not None:
            self.process.stdout.close()

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                output = self.process.stdout.read() if self.process.stdout else ""
                self.fail(f"Anna harness exited before readiness:\n{output}")
            try:
                with urllib.request.urlopen(
                    f"{self.base_url}/api/config", timeout=1
                ) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        self.fail("Anna harness did not become ready within 30 seconds")

    def _post(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def _call(
        self,
        session_id: str,
        namespace: str,
        method: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        return self._post(
            "/api/session/call",
            {
                "session_id": session_id,
                "ns": namespace,
                "method": method,
                "args": args,
            },
        )

    def test_storage_and_no_llm_tool_route(self) -> None:
        session = self._post("/api/session/create")
        session_id = str(session["session_id"])
        document = {
            "nextSeq": 2,
            "notes": [
                {
                    "id": "integration-note",
                    "text": "Follow up with the customer tomorrow.",
                    "seq": 1,
                    "createdAt": "2026-10-31T00:00:00.000Z",
                }
            ],
        }

        saved = self._call(
            session_id,
            "storage",
            "set",
            {"key": "notes", "value": document},
        )
        self.assertTrue(saved["ok"])

        loaded = self._call(session_id, "storage", "get", {"key": "notes"})
        self.assertTrue(loaded["ok"])
        self.assertEqual(loaded["result"]["value"], document)

        invoked = self._call(
            session_id,
            "tools",
            "invoke",
            {
                "tool_id": "tool-dev-mini-notes-summarizer",
                "method": "summarize",
                "args": {
                    "notes": [
                        {
                            "seq": 1,
                            "text": "Follow up with the customer tomorrow.",
                        }
                    ]
                },
                "timeoutMs": 80_000,
            },
        )

        self.assertFalse(invoked["ok"])
        self.assertEqual(invoked["error"]["code"], "tool_failed")
        self.assertIn(
            "harness started with --no-llm",
            invoked["error"]["message"],
        )


if __name__ == "__main__":
    unittest.main()
