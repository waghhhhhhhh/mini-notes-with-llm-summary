import type { AnnaRuntime, StorageGetResult } from "./runtime";
import { unwrapHostResult } from "./runtime";
import {
  NOTES_KEY,
  type LoadedNotes,
  type NotesDocument,
  normalizeNotesDocument,
} from "../notes/model";

export async function loadNotes(anna: AnnaRuntime): Promise<LoadedNotes> {
  const response = await anna.storage.get({ key: NOTES_KEY });
  const result = unwrapHostResult<StorageGetResult>(response);
  const exists = result?.exists ?? result?.value != null;

  return {
    document: exists
      ? normalizeNotesDocument(result.value)
      : normalizeNotesDocument(null),
    etag: result?.etag,
  };
}

export async function saveNotes(
  anna: AnnaRuntime,
  document: NotesDocument,
  etag?: string,
) {
  const response = await anna.storage.set({
    key: NOTES_KEY,
    value: document,
    ...(etag ? { if_match: etag } : {}),
  });
  return unwrapHostResult(response);
}
