#!/usr/bin/env python3
"""JSON-RPC over stdio plugin for Mini Notes summaries."""

from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any


PROTOCOL_VERSION_V2 = "2.0"
TOOL_NAME = "summarize"

MANIFEST: dict[str, Any] = {
    "name": "tool-dev-mini-notes-summarizer",
    "display_name": "Mini Notes Summarizer",
    "version": "0.1.0",
    "description": (
        "Summarizes the current Mini Notes collection through Anna host sampling."
    ),
    "host_capabilities": ["llm.sample"],
    "tools": [
        {
            "name": TOOL_NAME,
            "description": (
                "Summarize the current notes in two or three concise sentences."
            ),
            "timeout": 75,
            "parameters": [
                {
                    "name": "notes",
                    "type": "array",
                    "description": "Notes in display order.",
                    "items": {"type": "object"},
                    "required": True,
                }
            ],
        }
    ],
    "runtime": {
        "type": "python",
        "min_version": "3.11",
    },
}


class SamplingError(Exception):
    def __init__(
        self,
        code: int,
        message: str,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass
class PendingSampling:
    event: threading.Event
    response: dict[str, Any] | None = None


_stdout_lock = threading.Lock()
_pending_lock = threading.Lock()
_pending: dict[str, PendingSampling] = {}


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _send(message: dict[str, Any]) -> None:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    with _stdout_lock:
        sys.stdout.write(payload + "\n")
        sys.stdout.flush()


def _response(
    request_id: Any,
    *,
    result: Any = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is None:
        message["result"] = result
    else:
        message["error"] = error
    return message


def _handle_initialize(request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    offered = params.get("protocolVersion") or "1.1"
    negotiated = PROTOCOL_VERSION_V2 if offered == PROTOCOL_VERSION_V2 else "1.1"
    sampling_capabilities = (
        {"sampling": {}} if negotiated == PROTOCOL_VERSION_V2 else {}
    )
    server_info = {
        "name": MANIFEST["name"],
        "version": MANIFEST["version"],
    }

    return _response(
        request_id,
        result={
            "protocolVersion": negotiated,
            "server_info": server_info,
            # Keep both spellings during the current protocol transition.
            "serverInfo": server_info,
            "capabilities": sampling_capabilities,
            "client_capabilities": sampling_capabilities,
        },
    )


def _normalize_notes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("notes must be an array")

    notes: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        notes.append(item)

    return sorted(
        notes,
        key=lambda item: item.get("seq") if isinstance(item.get("seq"), int) else 0,
    )


def _sampling_prompt(notes: list[dict[str, Any]]) -> str:
    lines = [
        f"{index}. {str(note['text']).strip()}"
        for index, note in enumerate(notes, start=1)
    ]
    return (
        "Summarize the following notes for the user in two or three concise "
        "sentences. Preserve important names, dates, and action items. Return "
        "only the summary, without a preamble or Markdown heading.\n\n"
        + "\n".join(lines)
    )


def _sample_summary(notes: list[dict[str, Any]], invoke_id: str) -> dict[str, Any]:
    request_id = f"sampling-{uuid.uuid4()}"
    pending = PendingSampling(event=threading.Event())

    with _pending_lock:
        _pending[request_id] = pending

    _send(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "sampling/createMessage",
            "params": {
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": _sampling_prompt(notes),
                        },
                    }
                ],
                "maxTokens": 700,
                "systemPrompt": (
                    "You are a precise editorial assistant. Be concise and factual."
                ),
                "temperature": 0.2,
                "includeContext": "none",
                "metadata": {
                    "executa_invoke_id": invoke_id,
                    "tool": TOOL_NAME,
                    "note_count": len(notes),
                },
            },
        }
    )

    if not pending.event.wait(timeout=75):
        with _pending_lock:
            _pending.pop(request_id, None)
        raise SamplingError(-32005, "sampling/createMessage timed out")

    with _pending_lock:
        _pending.pop(request_id, None)
        response = pending.response

    if response is None:
        raise SamplingError(-32603, "sampling response was lost")
    if "error" in response:
        error = response.get("error") or {}
        raise SamplingError(
            int(error.get("code", -32603)),
            str(error.get("message", "sampling failed")),
            error.get("data"),
        )

    result = response.get("result") or {}
    content = result.get("content") or {}
    if isinstance(content, list):
        text = "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
    elif isinstance(content, dict):
        text = str(content.get("text", "")).strip()
    else:
        text = ""

    if not text:
        raise SamplingError(-32603, "sampling returned an empty summary")

    return {
        "summary": text,
        "model": result.get("model"),
        "usage": result.get("usage"),
        "stopReason": result.get("stopReason"),
    }


def _handle_invoke(request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    tool = params.get("tool")
    arguments = params.get("arguments") or {}
    context = params.get("context") or {}
    invoke_id = (
        context.get("invoke_id")
        or params.get("invoke_id")
        or params.get("invokeId")
        or ""
    )

    if tool != TOOL_NAME:
        return _response(
            request_id,
            error={"code": -32601, "message": f"Unknown tool: {tool}"},
        )

    try:
        notes = _normalize_notes(arguments.get("notes"))
        if not notes:
            raise ValueError("at least one note is required")
        data = _sample_summary(notes, str(invoke_id))
    except SamplingError as error:
        return _response(
            request_id,
            error={
                "code": error.code,
                "message": error.message,
                "data": error.data,
            },
        )
    except (TypeError, ValueError) as error:
        return _response(
            request_id,
            error={"code": -32602, "message": str(error)},
        )
    except Exception as error:  # noqa: BLE001
        _log(f"invoke failed: {error!r}")
        return _response(
            request_id,
            error={"code": -32603, "message": f"Tool execution failed: {error}"},
        )

    return _response(
        request_id,
        result={
            "success": True,
            "data": data,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )


def _dispatch_response(message: dict[str, Any]) -> bool:
    response_id = message.get("id")
    if response_id is None:
        return False

    with _pending_lock:
        pending = _pending.get(str(response_id))
        if pending is None:
            return False
        pending.response = message
        pending.event.set()
    return True


def _handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return _handle_initialize(request_id, params)
    if method == "describe":
        return _response(request_id, result=MANIFEST)
    if method == "health":
        return _response(
            request_id,
            result={"status": "ready", "message": "", "details": {}},
        )
    if method == "shutdown":
        return _response(request_id, result={"ok": True})
    if method == "invoke":
        return _handle_invoke(request_id, params)
    return _response(
        request_id,
        error={"code": -32601, "message": f"Method not found: {method}"},
    )


def _read_messages(pool: ThreadPoolExecutor) -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            _send(
                _response(
                    None,
                    error={"code": -32700, "message": f"Parse error: {error.msg}"},
                )
            )
            continue

        if not isinstance(message, dict):
            _send(
                _response(
                    None,
                    error={"code": -32600, "message": "Invalid request"},
                )
            )
            continue

        if "method" not in message:
            if not _dispatch_response(message):
                _log(f"unmatched response id={message.get('id')!r}")
            continue

        if message.get("method") == "invoke":
            pool.submit(_process_request, message)
        else:
            response = _handle_request(message)
            if response is not None and message.get("id") is not None:
                _send(response)


def _process_request(message: dict[str, Any]) -> None:
    response = _handle_request(message)
    if response is not None and message.get("id") is not None:
        _send(response)


def main() -> None:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    _log("mini-notes-summarizer started")
    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="invoke")
    try:
        _read_messages(pool)
    finally:
        pool.shutdown(wait=True, cancel_futures=False)
        _log("mini-notes-summarizer stopped")


if __name__ == "__main__":
    main()

