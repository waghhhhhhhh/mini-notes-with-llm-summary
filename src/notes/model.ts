export const NOTES_KEY = "notes";
export const SUMMARIZER_TOOL_ID = "tool-dev-mini-notes-summarizer";

export interface Note {
  id: string;
  text: string;
  seq: number;
  createdAt: string;
}

export interface NotesDocument {
  nextSeq: number;
  notes: Note[];
}

export interface LoadedNotes {
  document: NotesDocument;
  etag?: string;
}

export function emptyNotesDocument(): NotesDocument {
  return {
    nextSeq: 1,
    notes: [],
  };
}

function isNote(value: unknown): value is Note {
  if (!value || typeof value !== "object") {
    return false;
  }

  const note = value as Partial<Note>;
  return (
    typeof note.id === "string" &&
    typeof note.text === "string" &&
    Number.isInteger(note.seq) &&
    typeof note.createdAt === "string"
  );
}

function normalizeDocument(value: unknown): NotesDocument {
  if (!value || typeof value !== "object") {
    return emptyNotesDocument();
  }

  const candidate = value as Partial<NotesDocument>;
  const notes = Array.isArray(candidate.notes)
    ? candidate.notes.filter(isNote).sort((left, right) => left.seq - right.seq)
    : [];
  const maxSeq = notes.reduce((maximum, note) => Math.max(maximum, note.seq), 0);
  const nextSeq =
    Number.isInteger(candidate.nextSeq) && Number(candidate.nextSeq) > maxSeq
      ? Number(candidate.nextSeq)
      : maxSeq + 1;

  return { nextSeq, notes };
}

export function createNote(document: NotesDocument, text: string): NotesDocument {
  const trimmed = text.trim();
  if (!trimmed) {
    throw new Error("Write something first.");
  }

  const note: Note = {
    id: crypto.randomUUID(),
    text: trimmed,
    seq: document.nextSeq,
    createdAt: new Date().toISOString(),
  };

  return {
    nextSeq: document.nextSeq + 1,
    notes: [...document.notes, note],
  };
}

export function removeNote(
  document: NotesDocument,
  noteId: string,
): NotesDocument {
  return {
    ...document,
    notes: document.notes.filter((note) => note.id !== noteId),
  };
}

export function notesSnapshot(document: NotesDocument) {
  return document.notes.map((note) => ({
    seq: note.seq,
    text: note.text,
    createdAt: note.createdAt,
  }));
}

export function normalizeNotesDocument(value: unknown): NotesDocument {
  return normalizeDocument(value);
}

