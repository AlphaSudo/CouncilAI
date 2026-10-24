import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Copy, X } from "lucide-react";
import "./council-copy.css";

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Embedded browsers may deny the modern clipboard API. The fallback still
    // runs directly from a user click and never sends text over the network.
  }
  const active = document.activeElement as HTMLElement | null;
  const input =
    active instanceof HTMLTextAreaElement || active instanceof HTMLInputElement
      ? active
      : null;
  const caret = input
    ? ([
        input.selectionStart,
        input.selectionEnd,
        input.selectionDirection,
      ] as const)
    : null;
  const selection = window.getSelection();
  const ranges = selection
    ? Array.from({ length: selection.rangeCount }, (_, i) =>
        selection.getRangeAt(i).cloneRange(),
      )
    : [];
  const temporary = document.createElement("textarea");
  temporary.value = text;
  temporary.readOnly = true;
  temporary.style.cssText = "position:fixed;left:-10000px;top:0;";
  // A modal dialog makes the rest of the document inert. Keep the fallback
  // selection inside that dialog so it can actually receive focus and copy.
  (active?.closest("dialog[open]") || document.body).appendChild(temporary);
  try {
    temporary.select();
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    temporary.remove();
    active?.focus({ preventScroll: true });
    if (input && caret && caret[0] != null && caret[1] != null) {
      try {
        input.setSelectionRange(caret[0], caret[1], caret[2] || undefined);
      } catch {
        /* Some input types have no selection API. */
      }
    } else if (selection) {
      selection.removeAllRanges();
      ranges.forEach((range) => selection.addRange(range));
    }
  }
}

function ManualCopy({
  text,
  onClose,
  returnFocus,
}: {
  text: string;
  onClose: () => void;
  returnFocus: HTMLButtonElement | null;
}) {
  const content = useRef<HTMLTextAreaElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    content.current?.focus();
    content.current?.select();
    return () => returnFocus?.focus({ preventScroll: true });
  }, [returnFocus]);
  return createPortal(
    <div className="council-copy-backdrop">
      <section
        className="council-copy-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Copy text manually"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            onClose();
          }
          if (
            event.key === "Tab" &&
            event.shiftKey &&
            document.activeElement === close.current
          ) {
            event.preventDefault();
            content.current?.focus();
          }
          if (
            event.key === "Tab" &&
            !event.shiftKey &&
            document.activeElement === content.current
          ) {
            event.preventDefault();
            close.current?.focus();
          }
        }}
      >
        <header>
          <h2>Copy text</h2>
          <button
            ref={close}
            type="button"
            className="council-icon"
            onClick={onClose}
            aria-label="Close copy dialog"
          >
            <X size={18} />
          </button>
        </header>
        <p>
          Clipboard access is unavailable. The text is selected; press Ctrl+C or
          ⌘C to copy it.
        </p>
        <textarea
          ref={content}
          aria-label="Text to copy"
          value={text}
          readOnly
        />
      </section>
    </div>,
    returnFocus?.closest("dialog[open]") || document.body,
  );
}

export function CopyTextButton({
  text,
  label,
  disabled = false,
}: {
  text: string;
  label: string;
  disabled?: boolean;
}) {
  const trigger = useRef<HTMLButtonElement>(null);
  const [state, setState] = useState<"idle" | "copying" | "copied">("idle");
  const [manual, setManual] = useState(false);
  useEffect(() => {
    if (state !== "copied") return;
    const timer = window.setTimeout(() => setState("idle"), 2000);
    return () => window.clearTimeout(timer);
  }, [state]);
  return (
    <>
      <button
        ref={trigger}
        type="button"
        className={`council-icon council-copy ${state === "copied" ? "is-copied" : ""}`}
        aria-label={label}
        title={state === "copied" ? "Copied" : label}
        disabled={disabled || !text.trim() || state === "copying"}
        onClick={async () => {
          setState("copying");
          if (await copyText(text)) {
            setState("copied");
            requestAnimationFrame(() =>
              trigger.current?.focus({ preventScroll: true }),
            );
          } else {
            setState("idle");
            setManual(true);
          }
        }}
      >
        {state === "copied" ? (
          <Check size={16} aria-hidden="true" />
        ) : (
          <Copy size={16} aria-hidden="true" />
        )}
        <span className="council-copy-status" role="status">
          {state === "copied" ? "Copied" : ""}
        </span>
      </button>
      {manual && (
        <ManualCopy
          text={text}
          onClose={() => setManual(false)}
          returnFocus={trigger.current}
        />
      )}
    </>
  );
}
