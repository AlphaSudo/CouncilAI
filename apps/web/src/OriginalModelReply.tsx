import { useEffect, useState } from "react";
import { api } from "./api";
import { CouncilBody } from "./CouncilBody";
import { CopyTextButton } from "./CouncilCopy";
import type { Dict } from "./types";
import "./original-model-reply.css";

export function SavedModelReply({
  cid,
  message,
  onSource,
  onText,
}: {
  cid: string;
  message: Dict;
  onSource: (version: string, start: number, end: number) => void;
  onText?: (text: string) => void;
}) {
  const [reply, setReply] = useState<Dict | null>(null);
  const [error, setError] = useState("");
  const [original, setOriginal] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (reply && onText) onText(original ? reply.content : reply.readable);
  }, [reply, original, onText]);
  useEffect(() => {
    let active = true;
    setReply(null);
    setError("");
    api(`/chats/${cid}/messages/${message.id}/original`).then(
      (value) => {
        if (active) setReply(value);
      },
      (error) => {
        if (active) setError(error.message);
      },
    );
    return () => {
      active = false;
    };
  }, [cid, message.id, attempt]);
  return (
    <div className="original-model-reply">
      <div className="original-model-reply-tools">
        <span>Complete saved model reply</span>
        {reply && (
          <>
            <button
              type="button"
              onClick={() => setOriginal((value) => !value)}
            >
              {original ? "Readable view" : "Original text"}
            </button>
            <CopyTextButton
              text={original ? reply.content : reply.readable}
              label="Copy complete model reply"
            />
          </>
        )}
      </div>
      {!reply && !error && <p role="status">Loading saved reply…</p>}
      {error && (
        <p role="status">
          {error}{" "}
          <button
            type="button"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Reload saved reply
          </button>
        </p>
      )}
      {reply ? (
        original ? (
          <pre className="original-model-reply-text">{reply.content}</pre>
        ) : (
          <CouncilBody text={reply.readable} onSource={onSource} />
        )
      ) : (
        <CouncilBody text={message.content || ""} onSource={onSource} />
      )}
    </div>
  );
}

export function OriginalReplyDetails(
  props: Parameters<typeof SavedModelReply>[0],
) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="original-reply-details"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Full model reply</summary>
      {open && <SavedModelReply {...props} />}
    </details>
  );
}
