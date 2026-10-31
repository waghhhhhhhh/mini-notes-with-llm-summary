import { useCallback, useEffect, useRef, useState } from "react";
import {
  LoaderCircle,
  NotebookPen,
  Plus,
  Sparkles,
  StickyNote,
  Trash2,
  X,
} from "lucide-react";
import { connectAnna, errorMessage, type AnnaRuntime } from "../anna/runtime";
import { loadNotes, saveNotes } from "../anna/notes-service";
import { summarizeNotes } from "../anna/tools-service";
import {
  createNote,
  emptyNotesDocument,
  removeNote,
  type Note,
  type NotesDocument,
} from "../notes/model";

type BusyAction = "loading" | "saving" | "deleting" | "summarizing" | null;

export function App() {
  const [anna, setAnna] = useState<AnnaRuntime>();
  const [document, setDocument] = useState<NotesDocument>(emptyNotesDocument);
  const [etag, setEtag] = useState<string>();
  const [draft, setDraft] = useState("");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState<BusyAction>("loading");
  const [error, setError] = useState("");
  const documentRef = useRef(document);
  const etagRef = useRef(etag);

  documentRef.current = document;
  etagRef.current = etag;

  useEffect(() => {
    let active = true;

    async function boot() {
      try {
        const runtime = await connectAnna();
        const loaded = await loadNotes(runtime);
        if (!active) {
          return;
        }
        setAnna(runtime);
        setDocument(loaded.document);
        setEtag(loaded.etag);
      } catch (bootError) {
        if (active) {
          setError(errorMessage(bootError));
        }
      } finally {
        if (active) {
          setBusy(null);
        }
      }
    }

    void boot();
    return () => {
      active = false;
    };
  }, []);

  const persist = useCallback(
    async (nextDocument: NotesDocument) => {
      if (!anna) {
        throw new Error("Anna runtime is not connected.");
      }
      const saved = await saveNotes(anna, nextDocument, etagRef.current);
      setDocument(nextDocument);
      setEtag(saved?.etag);
    },
    [anna],
  );

  async function addNote(event: React.FormEvent) {
    event.preventDefault();
    if (!draft.trim() || busy) {
      return;
    }

    setBusy("saving");
    setError("");
    try {
      await persist(createNote(documentRef.current, draft));
      setDraft("");
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setBusy(null);
    }
  }

  async function deleteNote(note: Note) {
    if (busy) {
      return;
    }

    setBusy("deleting");
    setError("");
    try {
      await persist(removeNote(documentRef.current, note.id));
    } catch (deleteError) {
      setError(errorMessage(deleteError));
    } finally {
      setBusy(null);
    }
  }

  async function summarize() {
    if (!anna || busy || document.notes.length === 0) {
      return;
    }

    setBusy("summarizing");
    setError("");
    setSummary("");
    try {
      const newest = await loadNotes(anna);
      setDocument(newest.document);
      setEtag(newest.etag);
      setSummary(await summarizeNotes(anna, newest.document));
    } catch (summaryError) {
      setError(errorMessage(summaryError));
    } finally {
      setBusy(null);
    }
  }

  const isBusy = busy !== null;

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <NotebookPen size={20} strokeWidth={1.8} />
          </span>
          <div>
            <h1>Mini Notes</h1>
            <p>{document.notes.length} saved</p>
          </div>
        </div>
        <span className="storage-status">
          <span className="status-dot" />
          Anna storage
        </span>
      </header>

      <form className="composer" onSubmit={addNote}>
        <label className="sr-only" htmlFor="note-draft">
          New note
        </label>
        <input
          id="note-draft"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Write a short note"
          maxLength={500}
          autoComplete="off"
          disabled={busy === "loading"}
        />
        <button
          type="submit"
          className="primary-button"
          disabled={!draft.trim() || isBusy}
        >
          {busy === "saving" ? (
            <LoaderCircle className="spin" size={17} />
          ) : (
            <Plus size={17} />
          )}
          Save
        </button>
      </form>

      {error ? (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="icon-button"
            onClick={() => setError("")}
            aria-label="Dismiss error"
            title="Dismiss"
          >
            <X size={16} />
          </button>
        </div>
      ) : null}

      <section className="workspace" aria-label="Notes">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Inbox</span>
            <h2>Your notes</h2>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={() => void summarize()}
            disabled={isBusy || document.notes.length === 0}
          >
            {busy === "summarizing" ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Sparkles size={17} />
            )}
            Summarize
          </button>
        </div>

        {busy === "loading" ? (
          <div className="notes-list" aria-hidden="true">
            {[0, 1, 2].map((item) => (
              <div className="note-row skeleton" key={item}>
                <span className="note-index" />
                <span className="skeleton-line" />
              </div>
            ))}
          </div>
        ) : document.notes.length === 0 ? (
          <div className="empty-state">
            <StickyNote size={25} strokeWidth={1.5} />
            <p>No notes yet.</p>
          </div>
        ) : (
          <ol className="notes-list">
            {document.notes.map((note) => (
              <li className="note-row" key={note.id}>
                <span className="note-index">{note.seq}</span>
                <div className="note-copy">
                  <p>{note.text}</p>
                  <time dateTime={note.createdAt}>
                    {new Intl.DateTimeFormat(undefined, {
                      month: "short",
                      day: "numeric",
                    }).format(new Date(note.createdAt))}
                  </time>
                </div>
                <button
                  type="button"
                  className="icon-button delete-button"
                  onClick={() => void deleteNote(note)}
                  disabled={isBusy}
                  aria-label={`Delete note ${note.seq}`}
                  title="Delete note"
                >
                  {busy === "deleting" ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <Trash2 size={16} />
                  )}
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="summary-panel" aria-live="polite">
        <div className="summary-label">
          <Sparkles size={15} />
          Summary
        </div>
        {busy === "summarizing" ? (
          <div className="summary-waiting">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <p className={summary ? undefined : "muted"}>
            {summary || "Summarize your current notes when you need the short version."}
          </p>
        )}
      </section>
    </main>
  );
}

