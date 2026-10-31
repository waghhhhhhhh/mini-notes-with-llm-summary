import { describe, expect, it, vi } from "vitest";
import { loadNotes, saveNotes } from "../../src/anna/notes-service";
import type { AnnaRuntime } from "../../src/anna/runtime";
import { summarizeNotes } from "../../src/anna/tools-service";
import type { NotesDocument } from "../../src/notes/model";

function createRuntime() {
  const get = vi.fn();
  const set = vi.fn();
  const invoke = vi.fn();
  const runtime = {
    storage: { get, set },
    tools: { invoke },
  } as unknown as AnnaRuntime;

  return { runtime, get, set, invoke };
}

const document: NotesDocument = {
  nextSeq: 3,
  notes: [
    {
      id: "note-1",
      text: "Follow up with the customer",
      seq: 1,
      createdAt: "2026-10-31T00:00:00.000Z",
    },
    {
      id: "note-2",
      text: "Fix the login bug",
      seq: 2,
      createdAt: "2026-10-31T01:00:00.000Z",
    },
  ],
};

describe("Anna services", () => {
  it("loads notes through storage.get and preserves the etag", async () => {
    const { runtime, get } = createRuntime();
    get.mockResolvedValue({
      value: { ...document, notes: [...document.notes].reverse() },
      exists: true,
      etag: "etag-1",
    });

    const loaded = await loadNotes(runtime);

    expect(get).toHaveBeenCalledWith({ key: "notes" });
    expect(loaded.etag).toBe("etag-1");
    expect(loaded.document.notes.map((note) => note.seq)).toEqual([1, 2]);
  });

  it("saves notes through storage.set with optimistic concurrency", async () => {
    const { runtime, set } = createRuntime();
    set.mockResolvedValue({ etag: "etag-2" });

    const saved = await saveNotes(runtime, document, "etag-1");

    expect(set).toHaveBeenCalledWith({
      key: "notes",
      value: document,
      if_match: "etag-1",
    });
    expect(saved).toEqual({ etag: "etag-2" });
  });

  it("summarizes notes only through anna.tools.invoke", async () => {
    const { runtime, invoke } = createRuntime();
    invoke.mockResolvedValue({
      success: true,
      data: { summary: "A customer follow-up and a login bug fix." },
    });

    const summary = await summarizeNotes(runtime, document);

    expect(invoke).toHaveBeenCalledWith({
      tool_id: "tool-dev-mini-notes-summarizer",
      method: "summarize",
      args: {
        notes: [
          {
            seq: 1,
            text: "Follow up with the customer",
            createdAt: "2026-10-31T00:00:00.000Z",
          },
          {
            seq: 2,
            text: "Fix the login bug",
            createdAt: "2026-10-31T01:00:00.000Z",
          },
        ],
      },
      timeoutMs: 80_000,
    });
    expect(summary).toBe("A customer follow-up and a login bug fix.");
  });

  it("surfaces nested tool failures", async () => {
    const { runtime, invoke } = createRuntime();
    invoke.mockResolvedValue({
      success: true,
      data: { success: false, error: "sampling failed" },
    });

    await expect(summarizeNotes(runtime, document)).rejects.toThrow(
      "sampling failed",
    );
  });

  it("surfaces Host envelopes with their RPC code", async () => {
    const { runtime, invoke } = createRuntime();
    invoke.mockResolvedValue({
      ok: false,
      error: { code: -32603, message: "harness started with --no-llm" },
    });

    await expect(summarizeNotes(runtime, document)).rejects.toThrow(
      "[-32603] harness started with --no-llm",
    );
  });
});
