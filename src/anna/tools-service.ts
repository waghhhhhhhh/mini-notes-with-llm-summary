import type { AnnaRuntime } from "./runtime";
import { unwrapHostResult } from "./runtime";
import {
  notesSnapshot,
  resolveSummarizerToolId,
  type NotesDocument,
} from "../notes/model";

function findSummary(value: unknown): string | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }

  const record = value as Record<string, unknown>;
  if (typeof record.summary === "string" && record.summary.trim()) {
    return record.summary.trim();
  }

  for (const key of ["result", "data", "content"]) {
    const nested = findSummary(record[key]);
    if (nested) {
      return nested;
    }
  }

  return undefined;
}

function findToolError(value: unknown): string | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }

  const record = value as Record<string, unknown>;
  if (record.success === false) {
    if (typeof record.error === "string") {
      return record.error;
    }
    if (record.error && typeof record.error === "object") {
      const error = record.error as Record<string, unknown>;
      if (typeof error.message === "string") {
        return error.message;
      }
    }
  }

  for (const key of ["result", "data"]) {
    const nested = findToolError(record[key]);
    if (nested) {
      return nested;
    }
  }

  return undefined;
}

export async function summarizeNotes(
  anna: AnnaRuntime,
  document: NotesDocument,
): Promise<string> {
  const response = await anna.tools.invoke({
    tool_id: resolveSummarizerToolId(),
    method: "summarize",
    args: {
      notes: notesSnapshot(document),
    },
    timeoutMs: 80_000,
  });
  const payload = unwrapHostResult(response);
  const toolError = findToolError(payload);
  if (toolError) {
    throw new Error(toolError);
  }

  const summary = findSummary(payload);
  if (!summary) {
    throw new Error("The summarizer returned no text.");
  }

  return summary;
}
