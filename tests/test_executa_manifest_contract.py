from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTA_DIR = ROOT / "executas" / "mini-notes-summarizer"


class ExecutaManifestContractTest(unittest.TestCase):
    def test_identity_is_consistent_across_app_runtime_and_plugin(self) -> None:
        app_manifest = json.loads(
            (ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        executa_config = json.loads(
            (EXECUTA_DIR / "executa.json").read_text(encoding="utf-8")
        )
        plugin_manifest = json.loads(
            (EXECUTA_DIR / "manifest.json").read_text(encoding="utf-8")
        )

        required = app_manifest["required_executas"]
        self.assertEqual(len(required), 1)
        tool_id = required[0]["tool_id"]

        self.assertEqual(executa_config["tool_id"], tool_id)
        self.assertEqual(plugin_manifest["name"], tool_id)
        self.assertEqual(
            app_manifest["ui"]["host_api"]["tools"],
            [f"required:{tool_id}"],
        )
        self.assertIn(
            "tools.invoke",
            app_manifest["permissions"],
        )
        self.assertEqual(
            app_manifest["ui"]["host_api"]["storage"],
            ["get", "set"],
        )
        self.assertIn("llm.sample", plugin_manifest["host_capabilities"])
        self.assertEqual(
            [tool["name"] for tool in plugin_manifest["tools"]],
            ["summarize"],
        )

        frontend_model = (ROOT / "src" / "notes" / "model.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            f'SUMMARIZER_TOOL_ID = "{tool_id}"',
            frontend_model,
        )

        spec = importlib.util.spec_from_file_location(
            "mini_notes_summarizer_contract",
            EXECUTA_DIR / "mini_notes_summarizer.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)
        self.assertEqual(module.MANIFEST, plugin_manifest)


if __name__ == "__main__":
    unittest.main()
