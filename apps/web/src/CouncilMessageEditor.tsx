import { useEffect, useRef, useState } from "react";
import { LoaderCircle, X } from "lucide-react";
import type { Dict } from "./types";

export function CouncilMessageEditor({
  message,
  blocked,
  busy,
  error,
  unknownCharge,
  onClose,
  onSubmit,
  onPause,
}: {
  message: Dict;
  blocked: boolean;
  busy: boolean;
  error: string;
  unknownCharge: boolean;
  onClose: () => void;
  onSubmit: (text: string) => void;
  onPause: () => void;
}) {
  const [text, setText] = useState(message.content);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const panel = dialog.current;
    panel?.showModal();
    return () => {
      panel?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="council-edit-dialog"
      aria-labelledby="council-edit-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy && !blocked && text.trim()) onSubmit(text);
        }}
      >
        <header>
          <h2 id="council-edit-title">Edit message</h2>
          <button
            type="button"
            className="council-icon"
            aria-label="Close editor"
            disabled={busy}
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <label htmlFor="council-edited-message">Your message</label>
        <textarea
          id="council-edited-message"
          autoFocus
          maxLength={8000}
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
        />
        <p>
          The council will answer again from here. Later replies stay in the
          history as an earlier version. Previous charges stay counted.
        </p>
        {unknownCharge && (
          <p>
            The earlier request’s charge is unknown and stays reserved.
            Regenerating authorizes a new request.
          </p>
        )}
        {blocked && (
          <div>
            <p role="status">
              Wait for the current response before regenerating. Your edit stays
              here.
            </p>
            <button type="button" disabled={busy} onClick={onPause}>
              Pause after this response
            </button>
          </div>
        )}
        {error && <p role="alert">{error}</p>}
        <footer>
          <button type="button" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={busy || blocked || !text.trim()}>
            {busy && <LoaderCircle size={15} className="council-spin" />} Edit
            &amp; regenerate
          </button>
        </footer>
      </form>
    </dialog>
  );
}
