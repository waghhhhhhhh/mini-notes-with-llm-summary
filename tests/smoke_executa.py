from __future__ import annotations

import argparse
import json
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary")
    parser.add_argument("--expected-version")
    args = parser.parse_args()

    process = subprocess.Popen(
        [args.binary],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None

    try:
        for request_id, method in [(1, "initialize"), (2, "describe")]:
            request = {"jsonrpc": "2.0", "id": request_id, "method": method}
            if method == "initialize":
                request["params"] = {
                    "protocolVersion": "2.0",
                    "capabilities": {"sampling": {"modalities": ["text"]}},
                }
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            response = json.loads(process.stdout.readline())
            if response.get("id") != request_id:
                raise RuntimeError(f"unexpected response: {response}")

        manifest = response["result"]
        if manifest.get("name") != "tool-dev-mini-notes-summarizer":
            raise RuntimeError(f"unexpected manifest identity: {manifest.get('name')}")
        if "llm.sample" not in manifest.get("host_capabilities", []):
            raise RuntimeError("llm.sample capability is missing")
        if (
            args.expected_version
            and manifest.get("version") != args.expected_version
        ):
            raise RuntimeError(
                "unexpected manifest version: "
                f"{manifest.get('version')} != {args.expected_version}"
            )
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    print("executa smoke test passed")


if __name__ == "__main__":
    main()
