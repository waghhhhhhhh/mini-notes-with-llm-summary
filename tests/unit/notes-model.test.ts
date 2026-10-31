import { describe, expect, it } from "vitest";
import {
  createNote,
  emptyNotesDocument,
  normalizeNotesDocument,
  notesSnapshot,
  removeNote,
} from "../../src/notes/model";

describe("notes model", () => {
  it("creates a trimmed note with the next sequence number", () => {
    const document = createNote(emptyNotesDocument(), "  Follow up tomorrow  ");

    expect(document.nextSeq).toBe(2);
    expect(document.notes).toHaveLength(1);
    expect(document.notes[0]).toMatchObject({
      text: "Follow up tomorrow",
      seq: 1,
    });
    expect(document.notes[0].id).toBeTruthy();
    expect(document.notes[0].createdAt).toBeTruthy();
  });

  it("rejects empty notes", () => {
    expect(() => createNote(emptyNotesDocument(), "   ")).toThrow(
      "Write something first.",
    );
  });

  it("removes a note without renumbering remaining notes", () => {
    const first = createNote(emptyNotesDocument(), "First");
    const second = createNote(first, "Second");
    const remaining = removeNote(second, first.notes[0].id);

    expect(remaining.notes).toHaveLength(1);
    expect(remaining.notes[0]).toMatchObject({ text: "Second", seq: 2 });
    expect(remaining.nextSeq).toBe(3);
  });

  it("normalizes stored notes into sequence order", () => {
    const normalized = normalizeNotesDocument({
      nextSeq: 2,
      notes: [
        {
          id: "second",
          text: "Second",
          seq: 2,
          createdAt: "2026-10-31T00:00:00.000Z",
        },
        {
          id: "first",
          text: "First",
          seq: 1,
          createdAt: "2026-10-31T00:00:00.000Z",
        },
      ],
    });

    expect(normalized.notes.map((note) => note.text)).toEqual([
      "First",
      "Second",
    ]);
    expect(normalized.nextSeq).toBe(3);
  });

  it("builds a tool snapshot without internal ids", () => {
    const document = createNote(emptyNotesDocument(), "Prepare workshop notes");

    expect(notesSnapshot(document)).toEqual([
      {
        seq: 1,
        text: "Prepare workshop notes",
        createdAt: document.notes[0].createdAt,
      },
    ]);
  });
});
