from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = (
    ROOT
    / "executas"
    / "mini-notes-summarizer"
    / "mini_notes_summarizer.py"
)


class ExecutaProtocolTest(unittest.TestCase):
    process: subprocess.Popen[str]
    request_id: int

    def setUp(self) -> None:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        self.process = subprocess.Popen(
            [sys.executable, str(PLUGIN)],
            cwd=PLUGIN.parent,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.request_id = 0

    def tearDown(self) -> None:
        if self.process.poll() is None:
            assert self.process.stdin is not None
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.process.stdout is not None:
            self.process.stdout.close()
        if self.process.stderr is not None:
            self.process.stderr.close()

    def send(self, method: str, params: dict[str, Any] | None = None) -> int:
        self.request_id += 1
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        return self.request_id

    def read(self) -> dict[str, Any]:
        assert self.process.stdout is not None
        line = self.process.stdout.readline()
        self.assertTrue(line, "Executa closed stdout unexpectedly")
        return json.loads(line)

    def test_initialize_describe_and_sampling_invoke(self) -> None:
        initialize_id = self.send(
            "initialize",
            {
                "protocolVersion": "2.0",
                "clientInfo": {"name": "test", "version": "1.0"},
                "capabilities": {"sampling": {"modalities": ["text"]}},
            },
        )
        initialize = self.read()
        self.assertEqual(initialize["id"], initialize_id)
        self.assertEqual(initialize["result"]["protocolVersion"], "2.0")
        self.assertEqual(
            initialize["result"]["client_capabilities"],
            {"sampling": {}},
        )

        describe_id = self.send("describe")
        describe = self.read()
        self.assertEqual(describe["id"], describe_id)
        self.assertEqual(
            describe["result"]["name"],
            "tool-dev-mini-notes-summarizer",
        )
        self.assertEqual(
            describe["result"]["host_capabilities"],
            ["llm.sample"],
        )
        self.assertEqual(
            describe["result"]["tools"][0]["parameters"][0]["name"],
            "notes",
        )

        invoke_id = self.send(
            "invoke",
            {
                "tool": "summarize",
                "arguments": {
                    "notes": [
                        {
                            "seq": 1,
                            "text": "Follow up with the customer tomorrow.",
                        },
                        {"seq": 2, "text": "Fix the login bug."},
                    ]
                },
                "context": {"invoke_id": "invoke-test-123"},
            },
        )

        sampling = self.read()
        self.assertEqual(sampling["method"], "sampling/createMessage")
        self.assertEqual(
            sampling["params"]["metadata"]["executa_invoke_id"],
            "invoke-test-123",
        )
        self.assertIn(
            "Follow up with the customer tomorrow.",
            sampling["params"]["messages"][0]["content"]["text"],
        )

        assert self.process.stdin is not None
        self.process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": sampling["id"],
                    "result": {
                        "role": "assistant",
                        "content": {
                            "type": "text",
                            "text": "Two open items need attention: a customer follow-up and a login bug fix.",
                        },
                        "model": "fixture-model",
                    },
                }
            )
            + "\n"
        )
        self.process.stdin.flush()

        final = self.read()
        self.assertEqual(final["id"], invoke_id)
        self.assertTrue(final["result"]["success"])
        self.assertIn("customer follow-up", final["result"]["data"]["summary"])


if __name__ == "__main__":
    unittest.main()
